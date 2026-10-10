import os
import json
import requests

API_KEY = "3e76525b0df19cc13bba1a225d3e957d023cc2c0c9095a06b7b883914306059b"

def get_shopping():
    params = {
        "engine": "google_shopping",
        "q": "white leather sneakers",
        "gl": "in",
        "hl": "en",
        "num": 5,
        "api_key": API_KEY
    }
    r = requests.get("https://serpapi.com/search", params=params)
    data = r.json()
    with open("docs/samples/shopping_sample.json", "w") as f:
        json.dump(data, f, indent=2)
    
    results = data.get("shopping_results", [])
    if results:
        res = results[0]
        product_id = res.get("product_id")
        immersive_token = res.get("immersive_product_page_token")
        print("First result:", res.get("title"))
        print("Product ID:", product_id)
        print("Immersive Token:", immersive_token)
        return product_id, immersive_token
    return None, None

def get_immersive(token):
    params = {
        "engine": "google_immersive_product",
        "immersive_product_page_token": token,
        "gl": "in",
        "hl": "en",
        "api_key": API_KEY
    }
    r = requests.get("https://serpapi.com/search", params=params)
    data = r.json()
    with open("docs/samples/immersive_sample.json", "w") as f:
        json.dump(data, f, indent=2)
    print("Immersive response keys:", data.keys())
    if "sellers" in data:
        print("Sellers:", len(data["sellers"]))

def get_product(pid):
    params = {
        "engine": "google_product",
        "product_id": pid,
        "gl": "in",
        "hl": "en",
        "api_key": API_KEY
    }
    r = requests.get("https://serpapi.com/search", params=params)
    data = r.json()
    with open("docs/samples/product_sample.json", "w") as f:
        json.dump(data, f, indent=2)
    print("Product response keys:", data.keys())
    if "sellers_results" in data:
        print("Sellers Results:", len(data.get("sellers_results", {}).get("online_sellers", [])))


pid, token = get_shopping()
if token:
    print("\nFetching Immersive Product...")
    get_immersive(token)
if pid:
    print("\nFetching Product ID...")
    get_product(pid)
