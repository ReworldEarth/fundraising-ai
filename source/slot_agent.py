
import os
import yaml
import argparse
from dotenv import load_dotenv
from pathlib import Path
from langchain.prompts import ChatPromptTemplate
from langchain_mistralai.chat_models import ChatMistralAI
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
import json
from langgraph.graph import END

def read_config(name=''):
    if name == '':
        name = "config.yaml"
    with open(f"{name}", "r") as f:
        config = yaml.load(f,Loader=yaml.Loader)
    
    return config

def call_model(config):
    dotenv_path = Path(config['env_path'])
    load_dotenv(dotenv_path=dotenv_path)

    MY_KEY = os.getenv('MISTRAL_KEY')
    os.environ["MISTRAL_API_KEY"] = MY_KEY

    llm_mistral = ChatMistralAI(
                                    model=config['llm_chat_model'],
                                    temperature=0
                                )
    return llm_mistral 

SLOT_FILLER_PROMPT = ChatPromptTemplate.from_template("""
# You are a helpful assistant that extracts grant application slots from the user's message. 
# You have a warm and playful tone and casual language structure. Use adjective similar to - amazing, fun, great, love it etc.
# The 4 slots are:
- grant_type (e.g. seed, research, project, private, government)
- region (e.g. Kenya, Latin America, Africa)
- funding_focus (e.g. marine, reforestation)
- org_type (e.g. NGO, university, community group)

# You are provided with the following context 
- Current slot state: {slot_state}
- User message: {user_msg}                                             

# Your instructions as an extraction agent is
- Firstly, check if all the values are filled for all the keys in slot state. If all of them have a value and are not None or NUll.
  You need to respond with: We have all the information you need and thanks the user for all the details.                                               
- If you don't have all the values then ask a clarifying question about any of the slots which has None or NULL value. 
  While asking questions, provide some examples for the slot you are trying to fill.                                                                                           
                                                     

# Return 2 information:
- (1) Updated slot state with updated key, value pairs in json format
- (2) Next question you want to ask, please return None if you no longer want to ask any question    

# Output example below -                                                                                                                                                     
    slot_state: {'grant_type': 'government', 'region': None, 'funding_focus': 'marine', 'org_type': None},
    next_question: That sounds like an amazing project! To help you find the perfect government funding, 
                    could you tell me which region you're based in? For example, are you in Kenya,
                    Latin America, or another part of Africa?
                                                      
""")    

curr_dir = os.getcwd()
os.chdir(curr_dir)

config = read_config()
llm_mistral = call_model(config)

slot_agent = create_react_agent(
                                    model=llm_mistral,
                                    name="slot_agent",
                                    tools=[],
                                    prompt=SLOT_FILLER_PROMPT
                                )


def web_search(query: str) -> str:
    """Search the web for information."""
    return (
        "Here are the headcounts for each of the FAANG companies in 2024:\n"
        "1. **Facebook (Meta)**: 67,317 employees.\n"
        "2. **Apple**: 164,000 employees.\n"
        "3. **Amazon**: 1,551,000 employees.\n"
        "4. **Netflix**: 14,000 employees.\n"
        "5. **Google (Alphabet)**: 181,269 employees."
    )

rag_agent = create_react_agent(
    model=llm_mistral,
    tools=[web_search],
    name="RAG_expert",
    prompt="You are a world class researcher with access to web search. Do not do any math."
)


supervisor_prompt = ChatPromptTemplate.from_template("""
# You are a Grant Match Finder assistant whose job is to find the perfect grant for users.
# This job needs to be accomplished in 2 phases -
- (1) You need to find all the relevant information from the user before starting your search
      You go that by filling values for all the slots in this directionary 
      For that you will be using the agent called slot_agent.
- (2) Once you have all the values for the keys you can then call the rag_agent that will help you do a web search and find the
      matching grant

# You are not supposed to do any web search or filling the slot. Your primary task is to figure out the right agent to call based on
# the dictionary provided to you.
                                                                                                                                               
# You have a warm and playful tone and casual language structure. Use adjective similar to - amazing, fun, great, love it etc.

# You are provided with the following context 
- Current slot state: {slot_state}
- User message: {user_msg}

# Output Format
- (1) For slot_agent, you need to pass the user message as well as the slot state and in return get slot state information and the next question
      you need to ask your user to get more information. Ensure you use this question from slot_agent to converse with the user
- (1) For rag_agent, you need to provide it the final slot state with all the updated key and value pairs   
                                                      
""")   

def step_router(state):
    # Get the message content
    last_message = state["messages"][-1]["content"]
    slot_state = state.get("slot_state", {
        "grant_type": None,
        "region": None,
        "funding_focus": None,
        "org_type": None
    })

    # Decide whether to call slot_agent or rag_agent
    if all(slot_state.values()):
        # All slots are filled, so call RAG
        return "RAG_expert"
    else:
        # Still need to fill some slots
        return "slot_agent"

def prepare_slot_agent_input(state):
    return {
        "user_msg": state["messages"][-1]["content"],
        "slot_state": state.get("slot_state", {
            "grant_type": None,
            "region": None,
            "funding_focus": None,
            "org_type": None
        })
    }

def prepare_rag_input(state):
    return {
        "input": json.dumps(state.get("slot_state", {}))
    }

supervisor = create_supervisor(
                                    agents={
                                                "slot_agent": slot_agent,
                                                "RAG_expert": rag_agent
                                            },
                                    model=llm_mistral,
                                    prompt=supervisor_prompt,
                                    step_router=step_router,
                                    agent_input_mappings={
                                        "slot_agent": prepare_slot_agent_input,
                                        "RAG_expert": prepare_rag_input
                                    },
                                    output_mode="last_message",
                                    supervisor_name="supervisor"
                                )
                            

# Compile and run
app = supervisor.compile()
result = app.invoke({
    "messages": [
        {
            "role": "user",
            "content": "We're looking for government funding for our marine project"
        }
    ]
})

print(result)