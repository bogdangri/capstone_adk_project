# **Database Setup Automation with Agents** 

## **1\. Problem Statement**

In many enterprise environments, business teams constantly send small change requests for **catalog / configuration tables** in relational databases (for example: fee tariffs, domain values, parameters).

Today these changes are often processed manually by an analyst who:

1. Interprets the natural-language request.  
2. Find the right tables and rows.  
3. Writes SQL (INSERT/UPDATE) scripts.  
4. Executes them or passes them through review.

The project aims to **automate as much as possible** of this pipeline, while keeping **humans in the loop** for validation and execution.

---

## **2\. Solution Overview**

This project implements a **TEXT-TO-DML pipeline** using:

* A **PostgreSQL catalog** of “use cases” and table metadata.  
* **Embeddings** and similarity search to retrieve the most relevant use-case and tables.  
* **LLM agents (via Google ADK / Gemini)** to:  
  	Discover what SQL context is needed.  
  	Plan the DML operations.  
  	Generate executable SQL / PL/pgSQL scripts.  
* A **human review step** before anything is executed.

* At a high level:  
1. The business sends a free-text request (email, ticket, form).  
2. The system embeds and matches it against known use cases.  
3. It extracts the relevant tables and instructions into a **context bundle**.  
4. Downstream agents use the context bundle to:  
   * Probe current data (SELECT).  
   * Decide on the correct INSERT/UPDATE/DELETE.  
   * Generate a **safe, auditable DML script** as a PL/pgSQL DO block).

5. A human validates and runs the script.

---

## **3\. Architecture**

### **3.1 High-Level Diagram (Conceptual)**

    docs\Project_kaggle_diagram.png

### **3.2 Main Components**

#### **3.2.1 TABLE Catalogs and logs** 

Two main catalog tables are used:

* `setup.catalog_use_cases`

1. Stores **template use cases**:  
   `doc_id`, `title`, `request_text`, `solution_text`  
   `sql_info_text`, `sql_instr_text`  
   `tables_hint` (array of involved table names)  
   `embedding` (pgvector, e.g. `vector(768)`)

2. Each row describes a “pattern” of request and solution, e.g.

* `setup.catalog_tables`

  * Stores documentation for tables:

    * `schema_name`, `table_name`, `title`, `content`

  * Used to give the agent good context about table structure and semantics.

Script for this two catalog tables are stored in db\_setup folder : init\_setup.sql

For content in this two nomenclators I used script that are stored in catalogs folder  \- load\_tables\_app.py for create context about tables 

           \- load\_use\_case\_1.py,load\_use\_case\_2.py for every use\_case

For logging executions of program other two tables are used : 

*    `logs.db_pipeline_logs`   
  Store different informations in different stages of executions  
*    `logs.agent_llm_logs`   
  Store events created by agents  

Script for this two catalog tables are stored in db\_setup folder : init\_logs.sql

    

#### **3.2.2 Context Bundle Builder** 

The script `get_info_use_case.py` is responsible for:

1. Creating an **embedding** from a textual representation of the request (`search_text`) using Gemini (`text-embedding-004`).

2. Running a **pgvector similarity search** against `setup.catalog_use_cases`.

3. Selecting the **top use case(s)**.

4. Pulling in the referenced tables from `setup.catalog_tables`.

5. Packaging everything into a **single `context_bundle` JSON** that downstream agents can consume.

This JSON is passed to the **sequential agents**.

#### **3.2.3 Sequential LLM Agents (Google ADK)**

The agent pipeline (using Google ADK) typically looks like:

1. **SQL Discovery Agent**

   * Read `context_bundle`.

   * Generates **SELECT statements** to:  
     Count existing rows.  
     Find max primary keys.  
     Inspect current values.

   * Output key: `sql_probe`.

2. **DML Planning / Info Agent**

   * Takes `sql_probe` \+ `context_bundle`.

   * Decides:  
     Whether rows must be **inserted**, **updated**, or left alone.  
     Which columns need to change.

   * Produces a structured **plan** (JSON).

3. **DML Generator** 

   * Converts the plan into executable SQL / PL/pgSQL, e.g.:

4. **Human Validation Step**

   * Analist reviews the generated script.

   * Optionally runs it in the target PostgreSQL instance.

---

## **4\. Database**

* **PostgreSQL** Docker image with `pgvector`.  
* The “business catalog tables” are stored in public schema .  
* Script for this tables are stored in db\_setup folder : init\_public.sql

**5\. Data Files – Input & Output Folder**

All program inputs, intermediate artifacts, and generated outputs are stored in a single folder: Data\_files 

 **Input Files (Requests)**

Files provided **to the pipeline** as business requests:

* Used by `main_pipeline.py`  
* `Body_text is , in fact , free language request`

**Output files ( script )**  

`data_files/req_123458.sql`

**6\. Project structure**

project-root/

│

├── README.md

├── main\_pipeline.py

├── normalize\_request.py

├── get\_info\_use\_case.py

├── get\_sql\_info\_agent.py

├── get\_dml\_info\_agent.py

├── sequential\_adk\_agent.py

├── gen\_dml\_script\_file.py

├── \_\_Init\_\_.py

├── utils/

│   ├── config.py

│   ├── logging\_utils.py

│   ├── helpers.py

├── db\_setup/

│   ├── init\_setup.sql

│   ├── init\_logs.sql

│   ├── init\_public.sql

│   ├── docker-compose.yml      

│├── catalogs/

│   ├── load\_tables\_app.py

│   ├── load\_use\_case\_1.py

│   ├── load\_use\_case\_2.py│

├── logging/

│   ├── pipeline\_logs/

│   ├── agent\_logs/

└── docs/

    ├── architecture.png

 

