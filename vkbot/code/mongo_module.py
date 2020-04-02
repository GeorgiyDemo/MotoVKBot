from datetime import datetime, timedelta

import pymongo


class MongoParentClass:
    """Родительский класс для установки соединения"""

    def __init__(self, connection_str):
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
        self.settings_table = self.connection["settings"]

    def get_usersbytags(self, tag):
        """Получения id пользователей по определенной выборке тегов"""
        # Находим тег, берем данные и на основе этих данных отдаем id пользователей
        tag_fields_dict = self.tags_table.find_one({"name": tag}, {"_id": 0, "name": 0})
        result = self.users_table.find(tag_fields_dict, {"_id": 0, "user_id": 1})
        if result != None:
            return [e["user_id"] for e in result]
        return []

    def get_alltags(self):
        """Получение списка всех тегов"""
        r = self.tags_table.find(projection={"_id": 0, "name": 1})
        if r != None:
            return [e["name"] for e in r]
        return []

    def get_walldata(self, wall_id):
        """Проверка на существование поста на стене в БД"""
        r = self.wall_table.find_one({"wall_id": wall_id}, {"_id": 0})
        if r != None:
            return True
        return False

    def set_walldata(self, wall_id, tag=None):
        """Добавление данных о постах на стене группы"""
        self.wall_table.insert_one({"wall_id": wall_id, "tag": tag})

    def new_userdata(self, user_id, first_name, second_name, current_step):
        """Занесение начальных значений пользователя в БД"""
        self.users_table.insert_one({"user_id": user_id, "first_name": first_name, "second_name": second_name,
                                     "current_step": current_step, "moto_model": "-", "moto_type": "-",
                                     "price_type": "-", "priority_type": "-", "coupon_5": "-", "coupon_10": "-",
                                     "wish": "-", "posts_send": 0})

    def inc_user_postssend(self, user_id):
        """Осуществляет инкремент кол-ва новостей (posts_send) для указанного пользователя"""
        self.users_table.update_one({"user_id": user_id}, {"$inc": {"posts_send": 1}})

    def get_current_step(self, user_id):
        """Получение текущего шага пользователя"""
        r = self.users_table.find_one({"user_id": user_id}, {"_id": 0, "current_step": 1})
        if r == None:
            return 0
        return r["current_step"]

    def search_userdata(self, user_id):
        """Поиск пользователя"""
        if self.users_table.find_one({"user_id": user_id}) == None:
            return False
        return True

    def get_userdata(self, user_id):
        """Получение всех данных о пользователе по его user_id"""
        return self.users_table.find_one({"user_id" : user_id},{"_id" : 0})
    
    def update_userdata(self, user_id, *items):
        """Обновление произвольных данных пользователей в БД"""
        set_dict = {}
        for e in items:
            set_dict.update(e)
        self.users_table.update_one({"user_id": user_id}, {"$set": set_dict})

    def get_all_users(self):
        """Получение всех пользователей с БД"""
        return list(self.users_table.find())

    def get_wishbyuser(self, user_id):
        """Получение желания пользователя по его id"""
        r = self.users_table.find_one({"user_id": user_id}, {"_id": 0, "wish": 1})
        return r["wish"]

    def remove_userdata(self, user_id):
        """Удаление пользователя с БД"""
        self.users_table.delete_one({"user_id": user_id})
    
    def get_namebyuserid(self, user_id):
        """Получение имени пользователя по его id"""
        return self.users_table.find_one({"user_id": user_id})["first_name"]

    def get_replaceword(self):
        """Получение слова для его последующей замены на имя пользователя"""
        return self.settings_table.find_one({"name": "replace_word"})["value"]


class MongoTTLClass(MongoParentClass):
    def __init__(self, connection_str):
        super().__init__(connection_str)
        self.ttl_table = self.connection["ttl"]
        self.users_table = self.connection["users"]
        self.settings_table = self.connection["settings"]

    def create_ttl_table(self):
        """Ставит ttl по полю date_expire"""
        self.ttl_table.create_index("date_expire", expireAfterSeconds=0)

    def get_ttl_table(self, user_system_id):
        """Проверка на существование объекта в таблице"""

        if self.ttl_table.find_one({"user_id": user_system_id}) == None:
            return True
        return False

    def set_ttl_table(self, field, user_id):
        """Установка временных полей"""

        # Ищем id пользователя
        user_system_id = self.users_table.find_one({"user_id": user_id}, {"_id": 1})["_id"]

        # Ищем кол-во секунд в настройках
        field_seconds = self.settings_table.find_one({"name": field + "_time"})["value"]

        # Формируем дату
        utc_timestamp = datetime.utcnow()
        new_timestamp = utc_timestamp + timedelta(seconds=field_seconds)

        # Все это записываемм
        self.ttl_table.insert_one({"user_id": user_system_id, "transition": field, "date_expire": new_timestamp})


class MongoMsgClass(MongoParentClass):
    """Класс для получения текста ответных сообщений в зависимости от шага"""

    def __init__(self, connection_str):
        super().__init__(connection_str)
        self.msg_table = self.connection["out_messages"]
        self.users_table = self.connection["users"]

    def get_message(self, step, user_id):
        result = self.msg_table.find_one({"current_step": step}, {"message": 1, "_id": 0})["message"]

        # Если есть {account_username}, то его надо заменить на имя пользователя с БД
        if "{account_username}" in result:
            user_name = self.users_table.find_one({"user_id": user_id})["first_name"]
            result = result.replace("{account_username}", user_name)

        return result

class MongoCouponClass(MongoMainClass):
    """Класс для определения валидных купонов пользователя"""
    def __init__(self, connection_str):
        super().__init__(connection_str)
        self.coupon_table = self.connection["coupons"]
        self.admin_table = self.connection["admins"]

    def set_coupon5(self, user_id, step):
        """Выставляет купон 5 в БД на заданном шаге для конкретного user_id"""
        
        allowed_steps = {
            15 : "step15_coupon5_time",
            18 : "step18_coupon5_time"
        }

        if step in allowed_steps:

            # Ищем кол-во секунд в настройках
            field_seconds = self.settings_table.find_one({"name": allowed_steps[step]})["value"]
            # Формируем дату
            utc_timestamp = datetime.utcnow()
            new_timestamp = utc_timestamp + timedelta(seconds=field_seconds)
            #Запись
            self.coupon_table.insert_one({"user_id": user_id, "coupon_type": "coupon_5", "date_expire": new_timestamp})

        else:
            raise ValueError("Несуществующий шаг для купона 5","Некорректный вызов с шагом {}".format(step))
    
    def set_coupon10(self, user_id, step):
        """Выставляет купон 10 в БД на заданном шаге для конкретного user_id"""
        allowed_steps = {
            19 : "step19_coupon10_time"
        }
        if step in allowed_steps:
            field_seconds = self.settings_table.find_one({"name": allowed_steps[step]})["value"]
            # Формируем дату
            utc_timestamp = datetime.utcnow()
            new_timestamp = utc_timestamp + timedelta(seconds=field_seconds)
            self.coupon_table.insert_one({"user_id": user_id, "coupon_type": "coupon_10", "date_expire": new_timestamp})
        else:
            raise ValueError("Несуществующий шаг для купона 10","Некорректный вызов с шагом {}".format(step))
    
    def check_coupon5(self, user_id):
        """Проверка на актуальность купона на 5% для заданного user_id пользователя"""
        #Если пользователь дошел до N шага и при этом купон есть
        self.get_current_step(user_id)
        if self.get_current_step(user_id) > 14 and self.coupon_table.find_one({"user_id" : user_id,"coupon_type" : "coupon_5"}) != None:
            return True
        #Иначе купон уже истек
        return False

    def check_coupon10(self, user_id):
        """Проверка на актуальность купона на 10% для заданного user_id пользователя"""
        if self.get_current_step(user_id) > 18 and self.coupon_table.find_one({"user_id" : user_id,"coupon_type" : "coupon_10"}) != None:
            return True
        #Иначе купон уже истек
        return False

    def check_admin(self, user_id):
        """Проверка пользователя на админа"""
        if self.admin_table.find_one({"vk_id" : user_id}) != None:
            return True
        return False

    def create_ttl_table(self):
        """Ставит ttl по полю date_expire"""
        self.coupon_table.create_index("date_expire", expireAfterSeconds=0)
    
    def remove_coupon5(self, user_id):
        """
        Приостанавливает действие купона 5 для пользователя.
        Необходимо, если пользователь подтвердил использование купона, а он еще не удалился
        """
        r = self.coupon_table.delete_many({"user_id": user_id, "coupon_type": "coupon_5"})
        print(r)
    def remove_coupon10(self, user_id):
        """
        Приостанавливает действие купона 10 для пользователя.
        Необходимо, если пользователь подтвердил использование купона, а он еще не удалился
        """
        r = self.coupon_table.delete_many({"user_id": user_id, "coupon_type": "coupon_10"})
        print(r)