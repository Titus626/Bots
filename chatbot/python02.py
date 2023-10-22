import os
import random
import time
import nltk
import spacy
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import re
import psycopg2
import requests
import openai

openai.api_key = os.environ["OPENAI_API_KEY"]

class Chatlog:
    """
    A class that represents a chatlog.

    Attributes:
        chatroom_url (str): The URL of the chatroom.
        username (str): The username of the chatbot.
        password (str): The password of the chatbot.
        database_name (str): The name of the database.
        database_user (str): The username of the database user.
        database_password (str): The password of the database user.
        nlp (spacy.Language): The spacy language model for NLP tasks.

    Methods:
        get_user_profile(user_id): Gets the user profile for the given user ID.
    """

    def __init__(self, chatroom_url, username, password, database_name, database_user, database_password):
        self.chatroom_url = chatroom_url
        self.username = username
        self.password = password
        self.database_name = database_name
        self.database_user = database_user
        self.database_password = database_password
        self.nlp = spacy.load("en")  # Load the English language model

        self.conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database=database_name,
            user=database_user,
            password=database_password
        )
        self.cur = self.conn.cursor()

    def get_user_profile(self, user_id):
        """
        Gets the user profile for the given user ID.

        Args:
            user_id (int): The user ID.

        Returns:
            dict: The user profile.
        """
        sentiments = []
        topics = []

        self.cur.execute(
            "SELECT * FROM user_profiles WHERE user_id = %s",
            (user_id,)
        )
        profile = self.cur.fetchone()

        if profile:
            sentiments = [int(sentiment) for sentiment in profile[1].split(",")]
            topics = profile[2].split(",")

        return {
            "avg_sentiment": sum(sentiments) / len(sentiments),
            "most_common_topic": max(topics, key=topics.count)
        }

class Chatbot:
    """
    A class that represents a chatbot.

    Attributes:
        chatlog (Chatlog): The chatlog object.

    Methods:
        generate_response(message): Generates a response to the given message.
    """

    def __init__(self, chatlog):
        self.chatlog = chatlog

    def generate_response(self, message_dict):
        """
        Generates a response to the given message.

        Args:
            message_dict (dict): The message dictionary containing 'user' and 'message' keys.

        Returns:
            str: The response.
        """
        user_profile = self.chatlog.get_user_profile(message_dict["user"])
        sentiments = user_profile.get("avg_sentiment", 0)
        topics = user_profile.get("most_common_topic", "")

        prompt = ""
        if sentiments > 0:
            prompt += "The user seems happy."
        elif sentiments < 0:
            prompt += " The user seems upset."
        else:
            prompt += "The user has a neutral emotion."

        if topics:
            if topics == "technology":
                prompt += " They are interested in technology."
            elif topics == "sports":
                prompt += " They like talking about sports."
            elif topics == "politics":
                prompt += " They are focused on politics."

        prompt += " How should I respond?"

        response = openai.Completion.create(
            engine="davinci",
            prompt=prompt,
            temperature=0.7,
            max_tokens=100
        )
        return response["choices"][0]["text"]

if __name__ == "__main__":
    # Initialize Chatlog and Chatbot
    chatlog = Chatlog(
        chatroom_url="http://your-chat-room-url",
        username="your-username",
        password="your-password",
        database_name="your-db-name",
        database_user="your-db-username",
        database_password="your-db-password"
    )
    chatbot = Chatbot(chatlog)

    while True:
        # Get user's message
        message = input("Enter message: ")
        message_dict = {"user": "user-id", "message": message}

        # Generate response
        response = chatbot.generate_response(message_dict)
        print(f"Response: {response.strip()}")
