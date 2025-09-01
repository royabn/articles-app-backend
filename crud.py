from sqlalchemy.orm import Session
import models, schemas
from auth import get_password_hash
from typing import List

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_articles(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Article).filter(models.Article.owner_id == user_id).offset(skip).limit(limit).all()

def get_user_article_by_id(db: Session, article_id: int, user_id: int):
    return db.query(models.Article).filter(models.Article.id == article_id, models.Article.owner_id == user_id).first()

def create_user_article(db: Session, article: schemas.ArticleBase, user_id: int):
    db_article = models.Article(**article.model_dump(), owner_id=user_id)
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    return db_article

def delete_user_article(db: Session, article_id: int, user_id: int):
    # Ensure the article belongs to the user before deleting
    article = db.query(models.Article).filter(
        models.Article.id == article_id,
        models.Article.owner_id == user_id
    ).first()

    if article:
        db.delete(article)
        db.commit()
        return True # Indicate successful deletion
    return False # Article not found or not owned by user

def update_article_tags(db: Session, article: models.Article, tag_names: [str]):
    # Clear existing tags
    article.tags.clear()

    for tag_name in tag_names:
        # Check if tag exists, otherwise create it
        tag = db.query(models.Tag).filter(models.Tag.name == tag_name).first()
        if not tag:
            tag = models.Tag(name=tag_name)
            db.add(tag)
            db.commit()
            db.refresh(tag)
        article.tags.append(tag)
    db.commit()
    db.refresh(article)
    return article