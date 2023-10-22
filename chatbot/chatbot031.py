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
    def __init__(self, chatroom_url, username, password, database_name, database_user, database_password):
        self.chatroom_url = chatroom_url
        self.username = username
        self.password = password
        self.database_name = database_name
        self.database_user = database_user
        self.database_password = database_password
        self.nlp = spacy.load("en_core_web_sm")  

        self.conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database=database_name,
            user=database_user,
            password=database_password
        )
        self.cur = self.conn.cursor()
        self.upgrade_database()

    def upgrade_database(self):
        self.cur.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_profiles')"
        )
        user_profiles_table_exists = self.cur.fetchone()[0]

        self.cur.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'chatlog')"
        )
        chatlog_table_exists = self.cur.fetchone()[0]

        if not user_profiles_table_exists:
            self.cur.execute("""
                CREATE TABLE user_profiles (
                    user_id SERIAL PRIMARY KEY,
                    sentiments TEXT,
                    topics TEXT,
                    data JSONB
                )
            """)
            self.conn.commit()

        if not chatlog_table_exists:
            self.cur.execute("""
                CREATE TABLE chatlog (
                    entry_id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    message TEXT,
                    timestamp TIMESTAMP DEFAULT NOW()
                )
            """)
            self.conn.commit()

    def get_user_profile(self, user_id):
        sentiments = []
        topics = []
        data = {}

        self.cur.execute(
            "SELECT * FROM user_profiles WHERE user_id = %s",
            (user_id,)
        )
        profile = self.cur.fetchone()

        if profile:
            sentiments = [int(sentiment) for sentiment in profile[1].split(",")]
            topics = profile[2].split(",")
            data = profile[3]

        return {
            "user_id": user_id,
            "avg_sentiment": sum(sentiments) / len(sentiments),
            "most_common_topic": max(topics, key=topics.count),
            "data": data
        }

    def create_user_profile(self, user_id, sentiments, topics, data):
        sentiments_str = ",".join(str(sentiment) for sentiment in sentiments)
        topics_str = ",".join(topics)

        self.cur.execute(
            "INSERT INTO user_profiles (user_id, sentiments, topics, data) VALUES (%s, %s, %s, %s)",
            (user_id, sentiments_str, topics_str, data)
        )
        self.conn.commit()

    def update_user_profile(self, user_id, sentiments, topics, data):
        sentiments_str = ",".join(str(sentiment) for sentiment in sentiments)
        topics_str = ",".join(topics)

        self.cur.execute(
            "UPDATE user_profiles SET sentiments = %s, topics = %s, data = %s WHERE user_id = %s",
            (sentiments_str, topics_str, data, user_id)
        )
        self.conn.commit()

    def store_chatlog(self, user_id, message):
        self.cur.execute(
            "INSERT INTO chatlog (user_id, message) VALUES (%s, %s)",
            (user_id, message)
        )
        self.conn.commit()


class Chatbot:
    def __init__(self, chatlog):
        self.chatlog = chatlog

    def generate_response(self, message_dict):
        user_id = message_dict["user"]
        message = message_dict["message"]

        self.chatlog.store_chatlog(user_id, message)

        doc = self.chatlog.nlp(message)
        sentiments = [sentence._.sentiment.polarity for sentence in doc.sents]
        topics = [token.lemma_ for token in doc if token.pos_ in ["NOUN", "PROPN"]]

        user_profile = self.chatlog.get_user_profile(user_id)
        existing_sentiments = user_profile.get("avg_sentiment", [])
        existing_topics = user_profile.get("most_common_topic", [])
        existing_data = user_profile.get("data", {})

        updated_sentiments = existing_sentiments + sentiments
        updated_topics = existing_topics + topics

        if user_profile:
            self.chatlog.update_user_profile(user_id, updated_sentiments, updated_topics, existing_data)
        else:
            self.chatlog.create_user_profile(user_id, updated_sentiments, updated_topics, existing_data)

        response = "Thank you for your message. How can I assist you?"
        return response

    def process_command(self, command):
        response = openai.Completion.create(
            engine="davinci",
            prompt=command,
            temperature=0.7,
            max_tokens=100
        )
        return response.choices[0].text.strip()


def authenticate(username, password):
    expected_username = "your-username"
    expected_password = "your-password"

    if username == expected_username and password == expected_password:
        return True
    else:
        return False


def start_cli():
    username = input("Enter your username: ")
    password = input("Enter your password: ")

    authenticated = authenticate(username, password)

    if not authenticated:
        print("Authentication failed. Exiting...")
        return

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
        command = input("Enter command (chat, profile, command, exit): ")

        if command == "chat":
            user_id = input("Enter user ID: ")
            message = input("Enter message: ")
            message_dict = {"user": user_id, "message": message}
            response = chatbot.generate_response(message_dict)
            print(f"Response: {response}")

        elif command == "profile":
            user_id = input("Enter user ID: ")
            profile = chatlog.get_user_profile(user_id)
            print("User Profile:")
            print(f"User ID: {profile['user_id']}")
            print(f"Average Sentiment: {profile['avg_sentiment']}")
            print(f"Most Common Topic: {profile['most_common_topic']}")
            print("Data:")
            for key, value in profile['data'].items():
                print(f"{key}: {value}")

        elif command == "command":
            user_id = input("Enter user ID: ")
            command = input("Enter command: ")
            response = chatbot.process_command(command)
            print(f"Response: {response}")

        elif command == "exit":
            break

        else:
            print("Invalid command. Please try again.")


if __name__ == "__main__":
    start_cli()
