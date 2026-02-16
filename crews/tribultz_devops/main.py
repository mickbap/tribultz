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
    tasks_config = load_config('config/tasks.yaml')

    # Create Agents
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

    # Create Tasks
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

    # Instantiate Crew
    tribultz_crew = Crew(
        agents=[security_engineer, qa_engineer, devops_engineer],
        tasks=[task_scoping, task_isolation, task_migration, task_smoke],
        verbose=True,
        process=Process.sequential
    )

    # Dry run check
    if '--dry-run' in sys.argv:
        print("Dry run mode: Crew configuration loaded successfully.")
        print("Agents:", [agent.role for agent in tribultz_crew.agents])
        print("Tasks:", [task.description[:50] + "..." for task in tribultz_crew.tasks])
        return

    # Execute
    result = tribultz_crew.kickoff()
    print("Crew Execution Completed")
    print(result)

if __name__ == "__main__":
    main()
