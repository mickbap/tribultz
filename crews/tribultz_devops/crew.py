import os
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crews.tribultz_devops.tools.run_shell_tool import RunShellTool
from crews.tribultz_devops.tools.git_status_tool import GitStatusTool
from crews.tribultz_devops.tools.docker_verify_tool import DockerVerifyTool

@CrewBase
class TribultzDevOpsCrew:
    """Tribultz DevOps Crew"""
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    @agent
    def senior_devops_engineer(self) -> Agent:
        return Agent(
            config=self.agents_config['senior_devops_engineer'],
            tools=[RunShellTool.run_shell, GitStatusTool.git_status, DockerVerifyTool.docker_verify],
            verbose=True
        )

    @task
    def system_verification_task(self) -> Task:
        return Task(
            config=self.tasks_config['system_verification_task'],
            agent=self.senior_devops_engineer()
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=2,
        )
