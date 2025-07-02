import os
import yaml
import json
from dotenv import load_dotenv
from pathlib import Path
from langchain_mistralai.chat_models import ChatMistralAI
from langchain_core.messages import SystemMessage, HumanMessage,AIMessage


def read_config(config_path='config.yaml'):
    with open(config_path, "r") as f:
        return yaml.load(f, Loader=yaml.Loader)


def load_llm(config):
    dotenv_path = Path(config['env_path'])
    load_dotenv(dotenv_path=dotenv_path)
    os.environ["MISTRAL_API_KEY"] = os.getenv('MISTRAL_KEY')
    return ChatMistralAI(model=config['llm_chat_model'], temperature=0)


def update_slot_state(updated_slot, slot_state):
    for k, v in updated_slot.items():
        if k in slot_state:
            slot_state[k] = v
    return slot_state


def build_system_message():
    system_prompt = """
                You are a warm yet concise assistant helping users find the right biodiversity grants by collecting 
                4 key pieces of information.

                Your goal is to extract and validate these 4 slots:
                1. grant_type — Allowed values: "private grant", "private prize", "government grant" or "government prize"
                2. region — This must be a country (e.g. Kenya, Brazil). If it's a continent, ask for a specific country.
                            When asking clarifying questions be specific and give examples of countries within that continent or region. 
                            The hierarchy is: Continent → Country → Region → City → District/Neighborhood
                3. funding_focus — Must be related to biodiversity (e.g. marine conservation, reforestation, endangered species)
                4. org_type — Only "NGO (non-profit government organization)" or "NPO (non-profit organization)" are valid

                ## Instructions:
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
                                                                    
                4. If the user says "not sure", "don’t know", or asks for suggestions:
                - Please respond with: "No problem. Please visit us again once you have all the necessary details. We’ll be happy to help."  
                                                                                                                                                               
                5. Avoid repeating the same question more than twice if the user hasn’t given a valid value.
                - Instead, acknowledge their uncertainty and say: “We can move on and revisit this later.”

                6. DO NOT make any suggestions from your end

                ## Tone instructions:   
                1. If the user's input is valid and fills a required slot:
                - Acknowledge with warm, supportive tone like "Awesome!", "Great pick!", or "So helpful!"

                2. If the user's input is invalid, vague, or unsupported:
                - Do NOT use warm or validating language.
                - Use a neutral, concise tone when asking for clarification.
                                                                                                                                                                        
                3.If the user shares abusive, insensitive, or unsupported causes, or even irrelevant causes respond with:
                "Calm your hourses and I don’t support those causes." No exceptions.

                ## Output instructions:
                Return a JSON dictionary with only the slots that were updated in this specific user message. 
                Do NOT include any slot that wasn't mentioned or confirmed in this message. 
                NEVER guess or fill slots based on assumptions. Only extract information that is explicitly present.

                If the user does not provide any new valid info, keep the slot_state dictionary empty.

                Return a JSON dict in this format only:
                {{
                "slot_state": {{ "slot_name": "value" }}, // Only include keys for slots updated in this turn
                "next_question": string //Your next friendly question or a message if everything is complete"
                }}                  
                """
                

    return SystemMessage(content=system_prompt)



def build_json_schema():
    return {
        "title": "parsed_slots",
        "description": "This should have the updated slot and the next question to be asked",
        "type": "object",
        "properties": {
            "updated_slot_state": {
                "type": "object",
                "description": "Dictionary with updated slot values"
            },
            "next_question": {
                "type": "string",
                "description": "Next question to ask for missing information"
            }
        },
        "required": ["updated_slot_state", "next_question"]
    }

def run_chatbot():
    config = read_config()
    data_config = read_config(config_path='data_config.yaml')
    llm = load_llm(config).with_structured_output(build_json_schema())
    
    slot_state = {
        "grant_type": None,
        "region": None,
        "funding_focus": None,
        "org_type": None
    }

    chat_history = []  # All user + assistant messages stored here
    system_msg = build_system_message()  # Only defined once

    print("Welcome to the Grant Finder Chatbot! Type 'exit' to quit.")
    print("Let's start by gathering some key information to help find the right grants.\n")

    # Initial message
    initial_user_msg = HumanMessage(
        content=f"Here’s the current slot state: {slot_state}\nUser said: "
    )
    result = llm.invoke([system_msg, initial_user_msg])
    next_q = result['next_question']
    print(f"Chatbot: {next_q}\n")

    chat_history.append(AIMessage(content=next_q))  # Treat assistant responses as HumanMessage for context

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break

        # Add user message
        chat_history.append(HumanMessage(content=user_input))

        # Rebuild messages
        messages = [system_msg] + chat_history[-6:]  # Use last 6 for context
        messages.append(HumanMessage(
            content=f"Here’s the current slot state: {slot_state}\nUser said: {user_input}"
        ))
        result = llm.invoke(messages)

        slot_state = update_slot_state(result.get("updated_slot_state", {}), slot_state)
        # print("\nCurrent Slots:", slot_state)
        next_q = result["next_question"]

        if None in slot_state.values():
            print(f"Chatbot: {next_q}\n")
            chat_history.append(AIMessage(content=next_q))
        else:
            final_msg = "We have everything we need—thanks so much for all the amazing details!"
            print(f"Chatbot: {final_msg}")
            chat_history.append(AIMessage(content=final_msg))
            break

    output_path = f"{data_config['chat_history_output_path']}/{data_config['output_filename']}.json"
    final_output = {
        "chat_history": [{"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
                         for m in chat_history],
        "final_slot_state": slot_state
    }
    with open(output_path, "w") as f:
        json.dump(final_output, f, indent=4)

if __name__ == "__main__":
    run_chatbot()
