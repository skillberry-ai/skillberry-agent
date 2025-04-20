# blueberry-tools-agent

An AI system designed to automate gradual reprogramming of workflows with both existing and generated tools in such a way that the proportion of using high-quality deterministic tools increases on the paths most susceptible to hallucinations

## Features ✨

- **Improve AI accuracy and correctness**: Uses LLM and tools in tundam to improve accuracy and correctness.
- **Reduce AI systems TCO**: offloading computational processes to CPUs based deterministic tools.
- **Continuous performance improvement as part of inferencing**: gradualy reprogram workflows by generation and usage of high-quality deterministic tools.
- **Use case specific**: Provide value for repeated execution of workflows.
- **Tools usage**: Enforce usage of deterministic tools as part of AI systems.
- **Function calling**: Interface with tools-store-backends and search capabilities to efficiently use AI function calling.
- **Tools maker**: Interface with LLM-as-a-coder componets to generate hige-quality deterministic tools.
- **Operational API**: Expose LLM chat completion API allowing integration with any AI application, e.g., AI Agents
- **Configuration API**: Expose API allowing managment of configurations such as: tools store backend, coder backend, LLM used.

```mermaid
  graph TB
    subgraph BTM[blueberry tools maker]
        direction TB
        style BTM1 fill:#f99,stroke:#333,stroke-width:2px
        style BTM2 fill:#f99,stroke:#333,stroke-width:2px
        style BTM3 fill:#f99,stroke:#333,stroke-width:2px
        BTM1[Code Tool]
        BTM2[Generalize Tool]
        BTM3[Verify Tool]

        BTM1 --> BTM2
        BTM2 --> BTM3
    end
    click BTM1 "https://github.ibm.com/Blueberry/blueberry-tools-maker"
    click BTM2 "https://github.ibm.com/Blueberry/blueberry-tools-maker"
    click BTM3 "https://github.ibm.com/Blueberry/blueberry-tools-maker"

    subgraph BTS[blueberry tools service]
        direction TB
        style BTS1 fill:#99f,stroke:#333,stroke-width:2px
        style BTS2 fill:#99f,stroke:#333,stroke-width:2px
        style BTS3 fill:#99f,stroke:#333,stroke-width:2px
        style BTS4 fill:#99f,stroke:#333,stroke-width:2px
        style BTS5 fill:#99f,stroke:#333,stroke-width:2px
        BTS1[Tools CRUD]
        BTS2[Life Cycle Management]
        BTS3[Search Capabilities]
        BTS4[Execution]
        BTS5[Observability]
    end
    click BTS1 "https://github.ibm.com/Blueberry/blueberry-tools-service"
    click BTS2 "https://github.ibm.com/Blueberry/blueberry-tools-service"
    click BTS3 "https://github.ibm.com/Blueberry/blueberry-tools-service"
    click BTS4 "https://github.ibm.com/Blueberry/blueberry-tools-service"
    click BTS5 "https://github.ibm.com/Blueberry/blueberry-tools-service"

    subgraph BC[blueberry chatbot]
        style BC1 fill:#f9f,stroke:#333,stroke-width:2px
        BC1["Assistant ChatBot<br>(demo)"]
    end
    click BC1 "https://github.ibm.com/Blueberry/blueberry-chatbot"

    subgraph PA[Production Applications]
        style PA1 fill:#9f9,stroke:#333,stroke-width:2px
        PA1["Production Applications<br> (e.g., GenAI LH)"]
    end

    subgraph BTA[blueberry-tools-agent]
        style BTA1 fill:#ff9,stroke:#333,stroke-width:4px
        style BTA2 fill:#ff9,stroke:#333,stroke-width:4px
        style BTA3 fill:#ff9,stroke:#333,stroke-width:4px
        style BTA4 fill:#ff9,stroke:#333,stroke-width:4px
        style BTA5 fill:#ff9,stroke:#333,stroke-width:4px
        style BTA6 fill:#ff9,stroke:#333,stroke-width:4px
        BTA1>🖹 LLM API]
        BTA2>🧠 Suggest Useful Tools]
        BTA3>🔎 Find Existing Tools]
        BTA4>✍️ Code New Tools]
        BTA5>✅ Verify Tools]
        BTA6>🏃🏼‍♂️ Execute Tools]

        BTA1 ==> BTA2
        BTA2 ==> BTA3
        BTA3 ==> BTA4
        BTA4 ==> BTA5
        BTA5 ==> BTA6
        BTA6 ---> BTA1

    end

    BC1 --> BTA1
    PA1 --> BTA1
    BTA3 -. search .-> BTS
    BTA4 -. generate .-> BTM
    %% BTA6 -. execute .-> BTS
```
    
## Quickstart 🚀

### Start the Service

```bash
make docker_run
```

> Note: use `make help` for additional avaialbale operations

### Engage with the operational API (via OpenAPI) 📜

Open a browser against `http://127.0.0.1:7000/docs`.

### Prerequisites 🛠️

- Use the `.env` file to define the `RITS_API_KEY` variable:

```bash
RITS_API_KEY=********************************
```

### Local Installation 📦

```bash
cd ~
git clone git@github.ibm.com:Blueberry/blueberry-tools-agent.git
cd blueberry-tools-agent
pip install -r requirements.txt
```

### Start the Service 🚀

```bash
make run
```

### Engage with the configuration API 📜

Open a browser against `http://127.0.0.1:7001`.
