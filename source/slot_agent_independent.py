
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
You are a warm yet concise assistant helping users find the right biodiversity grants by collecting 4 key pieces of information. 
Use language—think "awesome", "love it", "so helpful", "great pick"—to make the experience fun and supportive when relevant information is provided
But you're also respectful and professional:
- If the user shares abusive, insensitive, or unsupported causes, or even irrelevant causes respond with: "Sorry, I don’t support those causes." No exceptions.

Your goal is to extract and validate these 4 slots:
1. grant_type — Allowed values: "private grant or private prize", "government grant or government prize"
2. region — This must be a country (e.g. Kenya, Brazil). If it's a region or continent, ask for a specific country.
3. funding_focus — Must be related to biodiversity (e.g. marine conservation, reforestation, endangered species)
4. org_type — Only "NGO (non-profit government organization)" or "NPO (non-profit organization)" are valid

Here’s what you’re given:
- slot_state: {slot_state}
- user_msg: {user_msg}

Here’s what you should do:
1. If all 4 slots have valid values (not None or "null"), respond with:
   "We have everything we need—thanks so much for all the amazing details!"

2. If any slot is missing or invalid:
   - Ask for the missing info with a friendly clarifying question.
   - Include 2–3 examples the user can pick from.
   - You need to enter this in the next_question section
                                                      
3. If a value doesn’t match what’s allowed:
   - Respond with - "Unfortunately, we don’t support this cause." 
     Don't respond with anything else, apart from you not supporting the cause
   - You need to enter this in the next_question section

Return a JSON dict:
{{
  "updated_slot_state": {{ "slot_name": "value" }},
  "next_question": string
}}
""")


slot_state = {
                "grant_type": None,
                "region": None,
                "funding_focus": None,
                "org_type": None
            }


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