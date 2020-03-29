import pymongo



class MongoParentClass:
    """Родительский класс для установки соединения"""
    def __init__(self, connection_str ):
        myclient = pymongo.MongoClient(connection_str)
        self.connection = myclient['MotoVKBot']

class MongoMainClass(MongoParentClass):
    """Класс для работы с пользователями"""
    def __init__(self, connection_str):
        super().__init__(connection_str)
        self.users_table = self.connection["users"]
        self.tags_table = self.connection["tags"]
        self.wall_table = self.connection["wall_archive"]
        self.ttl_table = self.connection["ttl"]

    def get_usersbytags(self, tag):
        """Получения id пользователей по определенной выборке тегов"""
        #Находим тег, берем данные и на основе этих данных отдаем id пользователей
        tag_fields_dict = self.tags_table.find_one({"name" : tag},{"_id": 0,"name": 0})
        result = self.users_table.find(tag_fields_dict,{"_id": 0,"user_id": 1})
        if result != None:
            return [e["user_id"] for e in result]
        return []
    
    def get_alltags(self):
        """Получение списка всех тегов"""
        r = self.tags_table.find(projection={"_id": 0,"name": 1})
        if r != None:
            return [e["name"] for e in r]
        return []

    def get_walldata(self, wall_id):
        """Проверка на существование поста на стене в БД"""
        r = self.wall_table.find_one({"wall_id" : wall_id},{"_id":0})
        if r != None:
            return True
        return False 

    def set_walldata(self, wall_id, tag=None):
        """Добавление данных о постах на стене группы"""
        self.wall_table.insert_one({"wall_id" : wall_id, "tag" : tag})

    def new_userdata(self, user_id, first_name, second_name, current_step):
        """Занесение начальных значений пользователя в БД"""
        self.users_table.insert_one({"user_id": user_id, "first_name": first_name, "second_name": second_name,
                              "current_step": current_step, "moto_model": "-", "moto_type": "-", "price_type": "-", "priority_type":"-","coupon_5":"-","coupon_10":"-", "posts_send" : 0})

    def inc_user_postssend(self, user_id):
        """Осуществляет инкремент кол-ва новостей (posts_send) для указанного пользователя"""
        self.users_table.update_one({"user_id" : user_id}, {"$inc": {"posts_send": 1}})
        
    def get_current_step(self, user_id):
        """Получение текущего шага пользователя"""
        r = self.users_table.find_one({"user_id": user_id},{"_id": 0,"current_step": 1})
        if r == None:
            return 0
        return r["current_step"]

    def search_userdata(self, user_id):
        """Поиск пользователя"""
        if self.users_table.find_one({"user_id": user_id}) == None:
            return False
        return True

    def update_userdata(self, user_id, *items):
        """Обновление произвольных данных пользователей в БД"""
        set_dict = {}
        for e in items: 
            set_dict.update(e)
        self.users_table.update_one({"user_id": user_id}, {"$set": set_dict})


class MongoTTLClass(MongoParentClass):
    def __init__(self, connection_str):
        super().__init__(connection_str)
        self.ttl_table = self.connection["ttl"]

    def create_ttl_table(self):
        """Ставит ttl по полю date_expire"""
        self.ttl_table.create_index("date_expire", expireAfterSeconds=0)   

    def set_ttl_table(self, time_ttl, field, user_id):
        """Установка временных полей"""
        self.ttl_table.create_index
        mongo_col.en("date", expireAfterSeconds=time_ttl)
        mongo_col.insert({'_id': 'session', "date": timestamp, "session": "test session"})


class MongoMsgClass(MongoParentClass):
    """Класс для получения текста ответных сообщений в зависимости от шага"""
    def __init__(self, connection_str):
        super().__init__(connection_str)
        self.msg_table = self.connection["out_messages"]
        self.user_table = self.connection["users"]
    
    def get_message(self, step, user_id):
        result = self.msg_table.find_one({"current_step": step}, {"message": 1, "_id": 0})["message"]

        #Если есть {account_username}, то его надо заменить на имя пользователя с БД
        if "{account_username}" in result:
            user_name = self.user_table.find_one({"user_id": user_id})["first_name"]
            result = result.replace("{account_username}",user_name)
        
        return result