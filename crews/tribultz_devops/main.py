import sys
import os
from crewai import Agent, Task, Crew, Process
import yaml


def load_config(file_path):
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    # Load configurations
    agents_config = load_config('config/agents.yaml')
    tasks_config  = load_config('config/tasks.yaml')

    # ── Agents ────────────────────────────────────────────────
    security_engineer = Agent(
        role=agents_config['security_engineer']['role'],
        goal=agents_config['security_engineer']['goal'],
        backstory=agents_config['security_engineer']['backstory'],
        verbose=True
    )

    qa_engineer = Agent(
        role=agents_config['qa_engineer']['role'],
        goal=agents_config['qa_engineer']['goal'],
        backstory=agents_config['qa_engineer']['backstory'],
        verbose=True
    )

    devops_engineer = Agent(
        role=agents_config['devops_engineer']['role'],
        goal=agents_config['devops_engineer']['goal'],
        backstory=agents_config['devops_engineer']['backstory'],
        verbose=True
    )

    secdevops_engineer = Agent(
        role=agents_config['secdevops_engineer']['role'],
        goal=agents_config['secdevops_engineer']['goal'],
        backstory=agents_config['secdevops_engineer']['backstory'],
        verbose=True
    )

    # ── Tasks originais ───────────────────────────────────────
    task_scoping = Task(
        description=tasks_config['enforce_tenant_scoping_all_routes']['description'],
        expected_output=tasks_config['enforce_tenant_scoping_all_routes']['expected_output'],
        agent=security_engineer
    )

    task_isolation = Task(
        description=tasks_config['add_tenant_isolation_tests']['description'],
        expected_output=tasks_config['add_tenant_isolation_tests']['expected_output'],
        agent=qa_engineer
    )

    task_migration = Task(
        description=tasks_config['alembic_baseline_migration']['description'],
        expected_output=tasks_config['alembic_baseline_migration']['expected_output'],
        agent=devops_engineer
    )

    task_smoke = Task(
        description=tasks_config['console_validate_report_smoke']['description'],
        expected_output=tasks_config['console_validate_report_smoke']['expected_output'],
        agent=qa_engineer
    )

    # ── Tasks SecDevOps ───────────────────────────────────────
    task_vm_hardening = Task(
        description=tasks_config['audit_vm_hardening']['description'],
        expected_output=tasks_config['audit_vm_hardening']['expected_output'],
        agent=secdevops_engineer
    )

    task_container_security = Task(
        description=tasks_config['audit_container_security']['description'],
        expected_output=tasks_config['audit_container_security']['expected_output'],
        agent=secdevops_engineer
    )

    task_nginx_headers = Task(
        description=tasks_config['audit_nginx_security_headers']['description'],
        expected_output=tasks_config['audit_nginx_security_headers']['expected_output'],
        agent=secdevops_engineer
    )

    task_secrets_hygiene = Task(
        description=tasks_config['audit_secrets_hygiene']['description'],
        expected_output=tasks_config['audit_secrets_hygiene']['expected_output'],
        agent=secdevops_engineer
    )

    task_deploy_rollback = Task(
        description=tasks_config['verify_deploy_rollback']['description'],
        expected_output=tasks_config['verify_deploy_rollback']['expected_output'],
        agent=devops_engineer
    )

    # ── Crew ─────────────────────────────────────────────────
    # Ordem de execução:
    # 1. SecDevOps: VM hardening → container security → nginx headers → secrets
    # 2. Security: tenant scoping
    # 3. QA: isolation tests → smoke
    # 4. DevOps: migrations → deploy rollback verification
    tribultz_crew = Crew(
        agents=[security_engineer, qa_engineer, devops_engineer, secdevops_engineer],
        tasks=[
            task_vm_hardening,
            task_container_security,
            task_nginx_headers,
            task_secrets_hygiene,
            task_scoping,
            task_isolation,
            task_smoke,
            task_migration,
            task_deploy_rollback,
        ],
        verbose=True,
        process=Process.sequential
    )

    # Dry run check
    if '--dry-run' in sys.argv:
        print("Dry run mode: Crew configuration loaded successfully.")
        print("Agents:", [agent.role for agent in tribultz_crew.agents])
        print("Tasks:",  [task.description[:60] + "..." for task in tribultz_crew.tasks])
        return

    # Execute
    result = tribultz_crew.kickoff()
    print("Crew Execution Completed")
    print(result)


if __name__ == "__main__":
    main()
