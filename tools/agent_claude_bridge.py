"""Owned Claude child transport, never a daemon or workflow acceptance engine.

This private entry point is prepared by ClaudeAdapter; public launchers do not
select it yet. Batch needs only the CLI. Interactive SDK imports stay optional.
All subprocesses inherit the supervisor's process group.
"""

import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys

from agent_claude import MAX_FRAME, native_arguments, result_event, settings


def emit(packet):
    print(json.dumps(packet), flush=True)


def coordinator(packet):
    origin = packet.get('origin')
    return (packet.get('parent_tool_use_id') is None
            and (origin is None or isinstance(origin, dict) and origin.get('kind') == 'human'))


def batch(executable, schema, run, model, effort, instructions):
    """Normalize only a successful native final envelope, never assistant prose."""
    command = [executable, '-p', '--output-format', 'json',
               *native_arguments(model, effort, schema, instructions)]
    # Inherit stdin/stderr and the process group recorded by shared supervision.
    with subprocess.Popen(command, stdout=subprocess.PIPE) as child:
        output = child.stdout.read(MAX_FRAME + 1)
        if len(output) > MAX_FRAME:
            child.kill()  # This exact child was created here, and is still unreaped.
            child.wait()
            raise ValueError('Claude native result exceeded the transport frame limit')
        status = child.wait()
    try:
        packet = json.loads(output)
    except ValueError:
        emit({'type': 'failure', 'category': 'malformed_result',
              'message': 'Claude returned no native result envelope'})
        return status or 1
    if not isinstance(packet, dict) or packet.get('type') != 'result' or not coordinator(packet):
        raise ValueError('Claude returned no attributable coordinator envelope')
    event = result_event(packet)
    emit(packet_for_result(packet))
    if status or event.kind == 'failure':
        return status if status > 0 else 1
    # The run is already private and owned by the launcher. Reuse its atomic
    # writer; the existing workflow validator owns schema/task/verdict checks.
    from detached_launcher import atomic
    atomic(run / 'agent-result.json', packet['structured_output'])
    return 0


def packet_for_result(packet, **fields):
    # No unknown payload, assistant reasoning, private error prose or helper text.
    keys = ('subtype', 'is_error', 'stop_reason', 'terminal_reason', 'api_error_status',
            'structured_output', 'usage', 'model_usage', 'total_cost_usd')
    result = {key: packet[key] for key in keys if key in packet}
    result.update(type='result', errors=bool(packet.get('errors')), **fields)
    return result


async def interactive(executable, schema, model, effort, instructions):
    from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient,
                                 ResultMessage, TextBlock)

    options = ClaudeAgentOptions(
        cli_path=executable, cwd=str(Path.cwd()), model=model, effort=effort,
        permission_mode='dontAsk', tools=['Read', 'Glob', 'Grep'],
        disallowed_tools=['Agent', 'Task', 'mcp__*'], strict_mcp_config=True,
        setting_sources=[], settings=json.dumps(settings()),
        system_prompt={'type': 'preset', 'preset': 'claude_code', 'append': instructions},
        output_format={'type': 'json_schema', 'schema': schema},
        extra_args={'safe-mode': None, 'restricted': None, 'permission-prompts': 'none',
                    'disable-slash-commands': None, 'no-session-persistence': None,
                    'no-chrome': None},
    )
    # Nonblocking stdin avoids leaving a reader thread alive after shutdown.
    loop = asyncio.get_running_loop()
    commands = asyncio.Queue()
    pending = bytearray()

    def read_input():
        try:
            data = os.read(sys.stdin.fileno(), 65536)
            if not data:
                loop.remove_reader(sys.stdin)
                commands.put_nowait(None)
                return
            pending.extend(data)
            while (end := pending.find(b'\n')) != -1:
                if end > MAX_FRAME:
                    raise ValueError('Claude bridge input is too large')
                commands.put_nowait(json.loads(pending[:end]))
                del pending[:end + 1]
            if len(pending) > MAX_FRAME:
                raise ValueError('Claude bridge input is too large')
        except (OSError, ValueError) as error:
            loop.remove_reader(sys.stdin)
            commands.put_nowait(error)

    turn = None
    last_turn = 0
    interrupted = False

    async with ClaudeSDKClient(options=options) as client:
        async def receive():
            nonlocal turn
            async for message in client.receive_messages():
                if isinstance(message, ResultMessage):
                    packet = asdict(message)
                    if turn is None or not coordinator(packet):
                        continue
                    emit(packet_for_result(packet, turn=turn))
                    turn = None
                elif isinstance(message, AssistantMessage) and turn is not None:
                    if message.parent_tool_use_id is None and not interrupted:
                        for index, block in enumerate(message.content):
                            if isinstance(block, TextBlock):
                                emit({'type': 'text', 'turn': turn,
                                      'id': f'{turn}:{index}', 'text': block.text})
                # Thinking, tools, helper output and unrecognized events stay private.
            raise ValueError('Claude SDK stream closed before transport shutdown')

        receiver = asyncio.create_task(receive())
        loop.add_reader(sys.stdin, read_input)
        emit({'type': 'ready'})
        try:
            while True:
                command_task = asyncio.create_task(commands.get())
                try:
                    done, _ = await asyncio.wait((receiver, command_task),
                                                 return_when=asyncio.FIRST_COMPLETED)
                    if receiver in done:
                        await receiver
                    command = command_task.result()
                finally:
                    if not command_task.done():
                        command_task.cancel()
                        await asyncio.gather(command_task, return_exceptions=True)
                if command is None:
                    return 0
                if isinstance(command, Exception):
                    raise command
                if not isinstance(command, dict) or type(command.get('turn')) is not int:
                    raise ValueError('Claude bridge received an invalid command')
                operation, number = command.get('operation'), command['turn']
                if operation == 'query' and turn is None and number == last_turn + 1:
                    if not isinstance(command.get('text'), str):
                        raise ValueError('Claude bridge query requires text')
                    turn = last_turn = number
                    interrupted = False
                    await client.query(command['text'])
                elif operation == 'interrupt' and number == last_turn:
                    interrupted = True
                    if turn is not None:
                        await client.interrupt()
                    # Even a late interrupt gets an acknowledgement. The protocol
                    # discards its candidate and gates cleanup until this settles.
                    emit({'type': 'ack', 'turn': number})
                else:
                    raise ValueError('Claude bridge command does not match the current turn')
        finally:
            loop.remove_reader(sys.stdin)
            receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)


def main():
    mode, executable, schema_path, run_path, model, effort, instructions = sys.argv[1:]
    schema = json.loads(Path(schema_path).read_text())
    if mode == 'batch':
        return batch(executable, schema, Path(run_path), model, effort, instructions)
    if mode == 'interactive':
        return asyncio.run(interactive(executable, schema, model, effort, instructions))
    raise ValueError('unknown Claude transport mode')


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        # SDK/CLI exception text may include private native packets or prompts.
        emit({'type': 'failure', 'category': 'process',
              'message': 'Claude transport failed; no workflow result accepted'})
        sys.exit(1)
