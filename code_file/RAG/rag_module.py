import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

def load_embeddings(filepath):
    vectors, texts, metadata = [], [], []
    with open(filepath, 'r') as f:
        for line in f:
            obj = json.loads(line)
            vectors.append(obj['embedding'])
            texts.append(obj.get('funding_name', 'No Name Provided'))
            metadata.append({
                "funder": obj.get("grant_funder", "N/A"),
                "amount": obj.get("funding_amount", "N/A"),
                "region": obj.get("geographic_focus", "N/A"),
                "focus": obj.get("funding_focus", "N/A"),
                "deadline": obj.get("application_deadline", "N/A"),
                "url": obj.get("Contact Information", "N/A")
            })
    return np.array(vectors).astype('float32'), texts, metadata

def setup_faiss(vectors):
    index = faiss.IndexFlatL2(len(vectors[0]))
    index.add(vectors)
    return index

def search_faiss(query, index, texts, metadata, embedder, k=3):
    q_emb = embedder.encode([query]).astype('float32')
    D, I = index.search(q_emb, k)
    return [(texts[i], metadata[i]) for i in I[0]]

def generate_rag_response(user_query, slot_state, retrieved_grants, llm):
    grant_summaries = "\n\n".join([
        f"Grant: {text}\n"
        f"- Funder: {meta['funder']}\n"
        f"- Amount: {meta['amount']}\n"
        f"- Region: {meta['region']}\n"
        f"- Focus: {meta['focus']}\n"
        f"- Deadline: {meta['deadline']}\n"
        f"- Website: {meta['url']}"
        for text, meta in retrieved_grants
    ])

    system_prompt = f"""
You are a helpful grant assistant. The user wants biodiversity-related funding.

Slot state: {slot_state}
Original user request: {user_query}

Based on these retrieved grants, generate a clear and helpful response in natural language. Do not repeat the grant info exactly – summarize and recommend them conversationally. Suggest next steps or application advice if possible.

Retrieved grant info:
{grant_summaries}
"""
    return llm.invoke(system_prompt).content


#Main Function

def main():
    print("Testing FAISS + embedding loading")

    # Update this path if necessary
    embedding_path = "data_with_embeddings.jsonl"

    vectors, texts, metadata = load_embeddings(embedding_path)
    print(f"Loaded {len(vectors)} embeddings")

    index = setup_faiss(vectors)
    embedder = SentenceTransformer("all-MiniLM-L6-v2")

    test_query = "marine conservation in Brazil"
    print(f"Running test search: {test_query}")
    results = search_faiss(test_query, index, texts, metadata, embedder, k=3)

    print("\nTop 3 Results:")
    for i, (title, meta) in enumerate(results, 1):
        print(f"\n{i}. {title}")
        for key, val in meta.items():
            print(f"   - {key.title()}: {val}")

if __name__ == "__main__":
    main()