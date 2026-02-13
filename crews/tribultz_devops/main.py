import os
import sys

# Ensure the project root is in sys.path to allow imports from 'crews.tribultz_devops'
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

def run():
    try:
        from crews.tribultz_devops.crew import TribultzDevOpsCrew
    except ImportError as e:
        print("Error: CrewAI is not installed. Please install 'crewai' and 'crewai-tools' to run this scaffold.")
        print(f"Details: {e}")
        sys.exit(1)

    # enforce dry run default
    if os.environ.get("DRY_RUN") is None:
        os.environ["DRY_RUN"] = "1"

    if os.environ.get("DRY_RUN") == "1":
        print("DRY RUN MODE ENABLED. No destructive changes will be applied.")
    
    TribultzDevOpsCrew().crew().kickoff()

if __name__ == "__main__":
    run()
