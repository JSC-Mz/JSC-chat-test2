from knowledge_loader import crawl_site, load_manuals
print("Refreshing JSC website...")
web = crawl_site(force=True)
print(f"Website chunks: {len(web)}")
print("Refreshing manuals...")
manuals = load_manuals(force=True)
print(f"Manual chunks: {len(manuals)}")
print("Done.")
