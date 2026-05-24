from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import json 
import os

app = FastAPI()
NEWS_FILE = './data/news.json'
UPLOAD_FOLDER = './data/images'

def get_image_path(id: str):
    return os.path.join(UPLOAD_FOLDER, f'{id}/image.jpg')

@app.get("/")
def get_news():
    
    with open(NEWS_FILE, 'r', encoding='utf-8') as f:
        news = json.load(f)

    news.sort(key = lambda x: x['date'], reverse=True)

    return news

@app.get("/images/{news_id}")
async def get_image(news_id: str):
    image_path = get_image_path(news_id)

    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    return FileResponse(
        image_path,
        media_type='image/jpeg',
        headers={"Cache-Control": "public, max-age=86400"}
    )