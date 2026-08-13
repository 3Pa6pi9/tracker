async def fetch_feed_max_speed(client, url, source, category):
    items = []
    try:
        # BYPASS CLOUDFLARE: Route through RSS2JSON API instead of fetching directly from Render
        api_url = f"https://api.rss2json.com/v1/api.json?rss_url={urllib.parse.quote(url)}"
        response = await client.get(api_url, timeout=10.0)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok":
                for entry in data.get("items", [])[:15]:
                    title = entry.get('title', '')
                    link = entry.get('link', '')
                    pub_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if title and link:
                        lat, lng = extract_geo(title)
                        items.append({
                            'title': title, 'link': link, 'source': source, 
                            'category': category, 'published_date': pub_date,
                            'threat_level': classify_threat(title), 'lat': lat, 'lng': lng
                        })
    except Exception as e:
        logger.error(f"Feed error {source}: {e}")
    return items
