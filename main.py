from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict
import wikipedia
import os
from dotenv import load_dotenv

load_dotenv()

from typing import List, Dict
import models, schemas, crud, auth
from database import engine, get_db
from fastapi.middleware.cors import CORSMiddleware


# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()
origins = [
    os.environ["FRONTEND_URL"]
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allows all headers in the request
)

# OAuth2 setup
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Auth Endpoints ---
@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/register", response_model=schemas.User)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)

@app.get("/users/me/", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    return current_user

# --- Wikipedia Search Endpoint ---
@app.get("/search", response_model=List[Dict[str, str]])
def search_wikipedia(query: str):
    try:
        results = wikipedia.search(query)
        summaries = []
        for title in results[:5]:
            try:
                page = wikipedia.page(title, auto_suggest=False)
                summaries.append({
                    "title": page.title,
                    "url": page.url,
                    "summary": wikipedia.summary(title, sentences=1)
                })
            except wikipedia.exceptions.PageError:
                continue
            except wikipedia.exceptions.DisambiguationError as e:
                # Handle disambiguation by picking the first option or skipping
                if e.options:
                    try:
                        page = wikipedia.page(e.options[0], auto_suggest=False)
                        summaries.append({
                            "title": page.title,
                            "url": page.url,
                            "summary": wikipedia.summary(e.options[0], sentences=1)
                        })
                    except:
                        continue
                continue
        return summaries
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Saved Articles Endpoints ---
@app.post("/articles/", response_model=schemas.ArticleCreate)
def save_article(article: schemas.ArticleBase, current_user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(get_db)):
    return crud.create_user_article(db=db, article=article, user_id=current_user.id)

@app.get("/articles/", response_model=List[schemas.ArticleWithTags])
def get_saved_articles(current_user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(get_db)):
    articles = crud.get_user_articles(db=db, user_id=current_user.id)

    articles = [
        {
            "id": str(article.id),
            "title": article.title,
            "owner_id": str(article.owner_id),
            "url": article.url,
            "tags": article.tags
        } for article in articles
    ]
    return articles

@app.delete("/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_article(article_id: int, current_user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(get_db)):
    success = crud.delete_user_article(db=db, article_id=article_id, user_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found or not owned by the current user"
        )

@app.put("/articles/{article_id}/tags", response_model=schemas.ArticleWithTags)
def update_article_tags(article_id: int, tags: List[str], current_user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(get_db)):
    article = crud.get_user_article_by_id(db=db, article_id=article_id, user_id=current_user.id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found or not owned by user")
    updated_article = crud.update_article_tags(db=db, article=article, tag_names=tags)
    updated_article = {
        "id": str(updated_article.id),
        "title": updated_article.title,
        "owner_id": str(updated_article.owner_id),
        "url": updated_article.url,
        "tags": updated_article.tags
    }
    return updated_article

# --- LLM Tagging Endpoint ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

@app.post("/articles/{article_id}/generate_tags", response_model=schemas.ArticleWithTags)
async def generate_article_tags(article_id: int, current_user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(get_db)):
    article = crud.get_user_article_by_id(db=db, article_id=article_id, user_id=current_user.id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found or not owned by user")

    # Get article content (summary is usually enough for tagging)
    try:
        page_summary = wikipedia.summary(article.title, sentences=3, auto_suggest=False)
        content = f"Title: {article.title}\nURL: {article.url}\nSummary: {page_summary}"
    except (wikipedia.exceptions.PageError, wikipedia.exceptions.DisambiguationError):
        content = f"Title: {article.title}\nURL: {article.url}" # Fallback if summary fails

    # Langchain integration with Gemini Pro
    # llm = ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=os.getenv("GEMINI_API_KEY"))
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.environ["GEMINI_API_KEY"]
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert article categorizer. Your task is to provide 3-5 relevant, comma-separated tags for the given article content. Be concise and use single words or short phrases."),
        ("user", "Article content: {content}\nTags:")
    ])
    output_parser = StrOutputParser()
    chain = prompt | llm | output_parser

    try:
        raw_tags = await chain.ainvoke({"content": content})
        tag_names = [tag.strip().lower() for tag in raw_tags.replace("\n", ",").split(',') if tag.strip()]
        if not tag_names:
            tag_names = article.title.lower().split()[:3]
        updated_article = crud.update_article_tags(db=db, article=article, tag_names=tag_names)
        updated_article = {
            "id": str(updated_article.id),
            "title": updated_article.title,
            "owner_id": str(updated_article.owner_id),
            "url": updated_article.url,
            "tags": updated_article.tags
        }
        return updated_article
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM tagging failed: {str(e)}")

@app.get("/health")
def health_check():
    return {"status": "ok"}

# run with 'uvicorn main:app --reload'