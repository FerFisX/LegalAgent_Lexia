from data_engineering.extraction.pdf_extractor import extract_pdf
from data_engineering.parsing.law_parser import parse_law
from data_engineering.chunking.chunker import chunk_law
from data_engineering.embeddings.chromadb_store import upsert_chunks, search, get_collection_stats

doc = extract_pdf('data/raw_pdfs/ley_prueba.pdf', doc_id='ley_prueba')
print("Paginas:", doc.total_pages)
print("Chars:", len(doc.full_text))

parsed = parse_law(doc.full_text, doc_id='ley_prueba', tipo='ley', numero='1', titulo='Ley de Prueba', areas=['civil'])
print("Articulos:", parsed.total_articles)

chunks = chunk_law(parsed)
print("Chunks:", len(chunks))

upsert_chunks(chunks)
print(get_collection_stats())

results = search('derechos y obligaciones')
for r in results[:3]:
    print(f"Art.{r['metadata']['article_number']} | Sim: {r['similarity']:.3f} | {r['text'][:80]}")
