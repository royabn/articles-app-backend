from pydantic import BaseModel
from typing import List, Optional

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    articles: List["Article"] = []

    class Config:
        from_attributes = True

class ArticleBase(BaseModel):
    title: str
    url: str

class TagBase(BaseModel):
    name: str

class Tag(TagBase):
    id: int

    class Config:
        from_attributes = True

class Article(ArticleBase):
    id: str
    owner_id: str
    tags: List[Tag] = []

    class Config:
        from_attributes = True

class ArticleCreate(ArticleBase):
    id: int
    owner_id: int
    tags: List[Tag] = []

    class Config:
        from_attributes = True

class ArticleWithTags(Article):
    tags: List[Tag] = []

    class Config:
        from_attributes = True

# JWT Token
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Update forward references
User.model_rebuild()
Article.model_rebuild()