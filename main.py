from src.tm_mongoService import MongoService

def main():
    mongo_service = MongoService(database="test_db")
    try:
        data="""
you are a helpfull assisatnt helloooo
"""
        db = mongo_service.database
        print(f"Connected to MongoDB database: {db.name}")
        rulebook_insert = mongo_service.insert_rulebook(data)
        rulebook_get = mongo_service.get_rulebook()
        rulebook_prompt = mongo_service.rulebook_prompt()

        print("rulebook insert:", rulebook_insert)
        print("rulebook get:", rulebook_get)
        print("rulebook prompt:", rulebook_prompt)


    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
    finally:
        mongo_service.close()

if __name__ == "__main__":
    main()
