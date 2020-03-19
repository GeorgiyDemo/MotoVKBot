import pymongo
class MongoUserClass:
    """Класс для работы с пользователями"""
    def __init__(self, connection):
        self.users_table = connection["users"]
        self.tags_table = connection["tags"]
        self.wall_table = connection["wall_archive"]

    def get_usersbytags(self, tag):
        """Получения id пользователей по определенной выборке тегов"""
        #Находим тег, берем данные и на основе этих данных отдаем id пользователей
        tag_fields_dict = self.tags_table.find_one({"name" : tag},{"_id": 0,"name": 0})
        print("tag_fields_dict {}".format(tag_fields_dict))
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
                              "current_step": current_step, "moto_model": "-", "moto_type": "-", "rudder_price": "-", "exhaustpipe_price":"-","wings_price":"-","optics_price":"-","all_price":"-"})

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


class MongoMsgClass:
    """Класс для получения текста ответных сообщений в зависимости от шага"""
    def __init__(self, connection):
        self.table = connection["out_messages"]
    
    def get_message(self, step):
        print("ПОПЫТКА ПОЛУЧИТЬ СООБЩЕНИЕ ДЛЯ ШАГА {}".format(step))
        result = self.table.find_one({"current_step": step}, {"message": 1, "_id": 0})
        return result["message"]
