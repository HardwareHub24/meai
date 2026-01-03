import os
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
sb = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

query = "How do I choose bolt preload and what safety factors are typical?"

query_embedding = openai_client.embeddings.create(
    model="text-embedding-3-small",
    input=query
).data[0].embedding

response = sb.rpc(
    "match_meai_chunks",
    {"query_embedding": query_embedding, "match_count": 8}
).execute()

print("\nTop matches:\n")
for row in response.data:
    print(f"{row['similarity']:.3f} | {row['source_file']} | chunk {row['chunk_index']}")
    print(row["content"][:300].replace("\n", " "))
    print("-" * 60)
