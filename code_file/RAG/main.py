import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from langchain_mistralai.chat_models import ChatMistralAI
from langchain.prompts import ChatPromptTemplate
from slot_agent import SLOT_FILLER_PROMPT, json_schema
from rag_module import load_embeddings, setup_faiss, search_faiss, generate_rag_response
from sentence_transformers import SentenceTransformer

# Load config
def read_config(path='config.yaml'):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

        

def call_model(config):
    load_dotenv(dotenv_path=config['env_path'])
    os.environ['MISTRAL_API_KEY'] = os.getenv('MISTRAL_KEY')
    return ChatMistralAI(model=config['llm_chat_model'], temperature=0)

def validate_slot(slot_name, value):
    if not value or not isinstance(value, str):
        return None

    value_lower = value.lower().strip()
    
    if slot_name == "grant_type":
        allowed = {
            "private": "private grant or private prize",
            "government": "government grant or government prize"
        }
        for k, v in allowed.items():
            if k in value_lower:
                return v
        return None

    if slot_name == "org_type":
        allowed = {
            "ngo": "NGO (non-profit government organization)",
            "npo": "NPO (non-profit organization)"
        }
        for k, v in allowed.items():
            if k in value_lower:
                return v
        return None

    if slot_name == "region":
        return value.title() if len(value.split()) == 1 else None

    if slot_name == "funding_focus":
        keywords = ["biodiversity", "marine", "species", "conservation", "reforestation"]
        return value if any(k in value_lower for k in keywords) else None

    return value

# Full Flow
def main():
    print("\n🌱 Welcome to the Unified Grant Finder Bot! Type 'exit' to quit.\n")

    config = read_config()
    llm = call_model(config)
    structured_llm = llm.with_structured_output(json_schema)
    embedder = SentenceTransformer("all-MiniLM-L6-v2")

    vectors, texts, metadata = load_embeddings(config['embedding_file'])
    index = setup_faiss(vectors)

    slot_state = {
        "grant_type": None,
        "region": None,
        "funding_focus": None,
        "org_type": None
    }

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ['exit', 'quit']:
            print("👋 Goodbye!")
            break
        if user_input.lower() == "start over":
            slot_state = {k: None for k in slot_state}
            print("🔄 Starting fresh. Tell me what kind of grant you're looking for.")
            continue

        messages = SLOT_FILLER_PROMPT.format_messages(slot_state=slot_state, user_msg=user_input)
        try:
            result = structured_llm.invoke(messages)
        except Exception as e:
            print("❌ Couldn't understand that. Try again.\n")
            continue

        updates = result.get("slot_state", {})
        for key in slot_state:
            if key in updates:
                validated = validate_slot(key, updates[key])
                if validated:
                    slot_state[key] = validated

        print("🧾 Slot State:", slot_state)

        if all(slot_state.values()):
            print("\n✅ All slots filled! Finding matching grants...\n")
            query = f"{slot_state['grant_type']} in {slot_state['region']} for {slot_state['funding_focus']} by {slot_state['org_type']}"
            results = search_faiss(query, index, texts, metadata, embedder)

            if not results:
                print("❌ No grants found. Try changing region or focus.\n")
                slot_state = {k: None for k in slot_state}
                continue

            rag_output = generate_rag_response(user_input, slot_state, results, llm)
            print(rag_output)

            print("\n🔁 Ask a new query or type 'start over' or 'exit'.")
            slot_state = {k: None for k in slot_state}
        else:
            print("🤖 Bot:", result.get("next_question", "❓ Please clarify your request."))

if __name__ == "__main__":
    main()
