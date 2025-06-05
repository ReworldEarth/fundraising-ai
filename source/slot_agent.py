
import os
import yaml
import argparse
from dotenv import load_dotenv
from pathlib import Path
from langchain.prompts import ChatPromptTemplate
from langchain_mistralai.chat_models import ChatMistralAI
from langgraph.prebuilt import create_react_agent
from langchain.agents import Tool
import json

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


curr_dir = os.getcwd()
os.chdir(curr_dir)

config = read_config()
llm_mistral = call_model(config)

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
                                                     

Return a JSON dict:
{{
  "updated_slots": {{ "slot_name": "value" }},
  "next_question": string
}}
""")    

slot_state = {
                "grant_type": None,
                "region": None,
                "funding_focus": None,
                "org_type": None
            }

def process_slot_output(response, slot_state):
    response_dict = json.loads(response)
    updated_slots = response_dict.get("updated_slots", {})
    next_question = response_dict.get("next_question")

    slot_state.update(updated_slots)
    return next_question, slot_state


json_schema = {
    "title": "parsed_slots",
    "description": "This should have the updated slot and the next question to be asked",
    "type": "object",
    "properties": {
        "slot_state": {
            "type": "object",
            "description": "This is the dictionary with updated states",
        },
        "next_question": {
            "type": "string",
            "description": "The next question you needs to as to fill in missing values in slot state",
        }
    },
    "required": ["slot_state", "next_question"],
}

if __name__ == "__main__":
    print("Welcome to the Grant Finder Chatbot! Type 'exit' to quit.\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break


        messages = SLOT_FILLER_PROMPT.format_messages(
                                                            slot_state=slot_state,
                                                            user_msg=user_input
                                                        )
        #print(messages)
        structured_llm = llm_mistral.with_structured_output(json_schema)
        result = structured_llm.invoke(messages)

        slot_state = result.get('slot_state')
        print(result.get('next_question'))
        print('\n')
        print(result)

# We're looking for government funding for our marine project