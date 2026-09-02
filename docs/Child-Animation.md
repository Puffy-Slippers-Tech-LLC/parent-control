# Gateway captive child animation

The kiosk gateway scene includes a standard Minecraft-style child whose story
plays continuously behind the request form.

## Character and staging

- The child is a recognisable, proportionate Minecraft figure: a connected,
  square-edged head, torso, arms, legs, and feet. It must not read as separate
  or floating body parts.
- At the start of each cycle, the child lies face up on the ground and faces
  the viewer.
- The head, arms, and upper torso are on the left side of the gateway.
- The lower body recedes through the gateway opening. Its yaw follows the
  gateway and floor perspective so it appears to pass behind the gateway,
  rather than float in front of it.
- The gateway boundary occludes the lower body. Only the portion within the
  opening is visible.
- A Minecraft diamond sword lies on the ground near the child.

## Chains

- The child starts tied down by chains at the wrists and lower body.
- Restraint chains use the same block-built violet-metal appearance and cyan
  edge lighting as the chains joining the request form to the gateway corners.
- They are thinner than the form chains, in proportion to the child.
- While restrained, the child struggles.
- When the chains break, their links shatter and land on the ground using the
  same chain material and visual language.

## Silent dialogue

- The child does not make audible sounds.
- The dialogue appears as one large word at a time, with a brief empty gap
  between words:

  1. `HURRY!`
  2. `MY`
  3. `WORLD`
  4. `IS`
  5. `DYING!!!`

- Dialogue sits immediately above the child’s head, entirely on the left of
  the gateway; it must not be positioned near the top of the gateway.
- Letters use Minecraft-like pixel blocks: gray faces, dark block outlines,
  and no smooth antialiasing.

## Cycle

1. For the first six seconds, the restrained child struggles while the silent
   words appear one at a time.
2. From six seconds, the chains break and their fragments fall to the ground.
3. By eight seconds, the child picks up the diamond sword, stands up, and
   raises it high in a ready-to-fight pose.
4. The story action completes at ten seconds.
5. The final raised-sword pose holds for three seconds.
6. The animation resets to the restrained, lying pose and repeats.

The active story action is therefore ten seconds; the complete repeating loop
is thirteen seconds.
