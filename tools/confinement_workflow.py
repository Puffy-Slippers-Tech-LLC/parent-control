"""Confinement policy; ordinary-plan mechanics belong to plan_launcher."""

from plan_launcher import PlanWorkflow, main as run_plan

WORKFLOW = PlanWorkflow('confinement', 'docs/confinement.md', effort='xhigh',
                        commit_prefix='Confinement', push=True, vm=True)


def main(argv=None):
    return run_plan(WORKFLOW, argv)
