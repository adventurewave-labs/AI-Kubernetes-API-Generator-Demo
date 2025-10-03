Project 3: The AI-Assisted Platform Extension GeneratorObjective: To build an AI agent that accelerates Kubernetes platform development. A platform engineer will provide a high-level, natural language request to create a new Kubernetes API (a CRD and controller). The agent will translate this request into the precise command-line arguments needed for openapi-mcp-codegen, execute the command, and generate the complete boilerplate Go project for the new controller.Core CNOE Repos Used:cnoe-io/openapi-mcp-codegen: The core code generation tool that the agent will wrap.cnoe-io/agentic-ai: The framework for building the "scaffolding" agent.cnoe-io/idpbuilder: The target platform where the newly generated controller can be tested.PrerequisitesGo programming language (1.19+) installed.Docker installed.git installed.An OpenAI API Key (or similar).A local development environment (e.g., VSCode).Architecture FlowPlatform Engineer      AI Scaffolding Agent        openapi-mcp-codegen       File System
      (CLI)               (Python Script)              (Go Binary)
        |                       |                         |                      |
1. "Create a VectorDB API" -->|                         |                      |
        |                       |                         |                      |
        |                  2. LLM constructs command    |                      |
        |                       |                         |                      |
        |                  3. Executes command with --> |                      |
        |                       |     args              |                      |
        |                       |                         |                      |
        |                       |<---------------------- 4. Generates Go project -->|
        |                       |                         |                      |
        |                       |                         |              5. Controller code
        |<-- "Done! Project at /path/to/vectordb"        |                is now available
        |                       |                         |                      |
Step-by-Step Implementation GuidePhase 1: Setup openapi-mcp-codegenClone and build the codegen tool:git clone [https://github.com/cnoe-io/openapi-mcp-codegen.git](https://github.com/cnoe-io/openapi-mcp-codegen.git)
cd openapi-mcp-codegen
go build .
# Move the binary to a location in your PATH for easy access
sudo mv openapi-mcp-codegen /usr/local/bin/
Run the tool manually to understand it: Experiment with a command to see what it generates. This is crucial for writing the agent's prompt.# This command tells the tool to create an API for 'VectorDB'
# in the group 'platform.acme.io' version 'v1alpha1'
# with spec fields 'size' (string) and 'replicas' (integer).
openapi-mcp-codegen \
  --output-dir /tmp/test-vectordb \
  --go-header-file hack/boilerplate.go.txt \
  --input-spec '{"group":"platform.acme.io","version":"v1alpha1","kind":"VectorDB","spec":{"properties":{"size":{"type":"string"},"replicas":{"type":"integer"}}}}'
Inspect the output in /tmp/test-vectordb. You'll see a complete Go project for a Kubernetes controller. This is what our agent needs to generate.Phase 2: Develop the Scaffolding AgentSet up the Python environment:mkdir ~/agentic-codegen-agent && cd ~/agentic-codegen-agent
python -m venv venv
source venv/bin/activate
pip install openai
Set your API key:export OPENAI_API_KEY='your_openai_key'
Create the agent script (agent.py): The core of this agent is the system prompt that teaches the LLM how to behave.import os
import subprocess
import openai
import json

# --- The Core Logic: The System Prompt ---
# This prompt is the "brain" of our agent. It tells the LLM its role and how to format its output.
SYSTEM_PROMPT = """
You are an expert Kubernetes Platform Engineering assistant. Your sole purpose is to translate natural language requests for new Kubernetes APIs into the precise JSON needed for the 'openapi-mcp-codegen' tool.

The user will describe an API they want. You must parse their request for the following information:
1.  **group**: A reverse-DNS style group name (e.g., `platform.acme.io`). Default to `platform.cnoe.io` if not specified.
2.  **version**: The API version (e.g., `v1alpha1`). Default to `v1alpha1`.
3.  **kind**: The CamelCase name of the resource (e.g., `VectorDB`, `CacheCluster`).
4.  **spec properties**: The fields inside the `.spec` of the resource. You must infer the type (string, integer, boolean).

You MUST format your response as a single, minified JSON object containing one key: "command". The value of this key is an array of strings representing the full command and its arguments.

Example User Request: "I need a `Notebook` CRD for our data science team. It should have a `cpu` field and a `memory` field, both strings."
Your Expected JSON Response:
{"command": ["openapi-mcp-codegen", "--output-dir", "/tmp/notebook", "--go-header-file", "hack/boilerplate.go.txt", "--input-spec", "{\"group\":\"datascience.cnoe.io\",\"version\":\"v1alpha1\",\"kind\":\"Notebook\",\"spec\":{\"properties\":{\"cpu\":{\"type\":\"string\"},\"memory\":{\"type\":\"string\"}}}}"]}

Example User Request: "Make me a simple `ClusterClaim` API with a `clusterId` string field."
Your Expected JSON Response:
{"command": ["openapi-mcp-codegen", "--output-dir", "/tmp/clusterclaim", "--go-header-file", "hack/boilerplate.go.txt", "--input-spec", "{\"group\":\"platform.cnoe.io\",\"version\":\"v1alpha1\",\"kind\":\"ClusterClaim\",\"spec\":{\"properties\":{\"clusterId\":{\"type\":\"string\"}}}}"]}
"""

def generate_codegen_command(user_request: str):
    print("Agent: Thinking...")
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4", # Or gpt-3.5-turbo
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_request},
        ],
        response_format={"type": "json_object"}
    )

    content = response.choices[0].message.content
    return json.loads(content)

def execute_command(command_data: dict):
    command_array = command_data.get("command")
    if not command_array:
        print("Error: LLM did not return a valid command.")
        return

    # Add the path to the boilerplate file from the cloned repo
    # This assumes the agent is run from its own directory, and the codegen repo is a sibling.
    command_array[4] = "../openapi-mcp-codegen/hack/boilerplate.go.txt"

    print(f"Agent: I have constructed the following command:\n{' '.join(command_array)}\n")
    print("Agent: Executing command...")

    try:
        # We use shell=False and pass args as a list for security
        subprocess.run(command_array, check=True)
        output_dir = command_array[2]
        print(f"\nSuccess! Your new controller project is ready at: {output_dir}")
    except subprocess.CalledProcessError as e:
        print(f"Error executing codegen command: {e}")
    except FileNotFoundError:
        print("Error: `openapi-mcp-codegen` not found in PATH. Did you build and install it?")


if __name__ == "__main__":
    request = input("Describe the Kubernetes API you want to create: ")

    # This is the agentic step: LLM generating a tool command
    command_json = generate_codegen_command(request)

    # This is the execution step
    execute_command(command_json)

Phase 3: Run and DemonstratePosition your directories: Make sure your agent's directory (agentic-codegen-agent) and the openapi-mcp-codegen directory are siblings./projects/
├── agentic-codegen-agent/
│   └── agent.py
└── openapi-mcp-codegen/
    └── hack/boilerplate.go.txt
Run the agent:cd ~/agentic-codegen-agent
python agent.py
Interact with the agent: When prompted, give it a natural language request.Describe the Kubernetes API you want to create: I need to create a VectorDB API for our new AI platform. The spec should include a string for engine_type (like 'pinecone' or 'weaviate') and an integer for the number of replicas.Observe the output:The agent will print the command it constructed.It will then execute the command.Finally, it will tell you where the generated project is located (e.g., /tmp/vectordb).Verify the result:List the contents of the output directory (ls -l /tmp/vectordb). You should see main.go, api/, internal/, etc.You have successfully generated a complete, compilable Kubernetes controller from a single sentence.How to DemonstrateRecord a terminal session.Briefly show the agent's Python code, especially the system prompt.Run the agent and enter your natural language request.Show the command the agent generates and executes.Do a tree or ls -R on the output directory to show the complete project structure that was created.Bonus: Open the generated api/v1alpha1/vectordb_types.go file to show that the engine_type and replicas fields are correctly defined in the Go struct.Advanced Bonus: cd into the generated directory, run docker build ., and show that the controller builds successfully into a container image.