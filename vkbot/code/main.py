# https://oauth.vk.com/authorize?client_id=5155010&redirect_uri=https://oauth.vk.com/blank.html&display=page&scope=offline,groups&response_type=token&v=5.37
# TODO Удаление пользователя по команде СТОП
# TODO ренейм всех шагов
import multiprocessing as mp
import time

import requests
import util_module
import vk_api
from mongo_module import MongoMainClass, MongoMsgClass, MongoTTLClass
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id


class WallMonitoringClass:
    """Класс в отдельном процессе для мониторинга стены"""

    def __init__(self, user_token, club_token, group, connection_str):
        self.user_vk = vk_api.VkApi(token=user_token)
        self.club_vk = vk_api.VkApi(token=club_token)
        # Взаимодействие с БД пользователей
        self.mongo_obj = MongoMainClass(connection_str)
        self.group = group
        self.user_alerts_dict = {}
        while True:
            self.monitoring()
            self.user_alerting()
            time.sleep(60)

    # Мониторим последние 3 записи т.к может быть такое, что проставили хештеги проще
    def monitoring(self):
        # Словарь пользователей и новости
        user_alerts_dict = {}
        tags_list = self.mongo_obj.get_alltags()
        results = self.user_vk.method(
            "wall.get", {"owner_id": self.group, "count": 3})
        for result in results["items"]:
            for tag in tags_list:
                # Если есть тег и этой записи еще нет в БД
                if tag in util_module.wallpost_check(result["text"]) and not self.mongo_obj.get_walldata(
                        "wall{}_{}".format(self.group, result["id"])):
                    user_lists = self.mongo_obj.get_usersbytags(tag)
                    wall_id = "wall{}_{}".format(self.group, result["id"])
                    user_alerts_dict[wall_id] = user_lists
                    # Выставляем данные в БД
                    self.mongo_obj.set_walldata(wall_id, tag)

        # Выставляем данные для user_alerting
        self.user_alerts_dict = user_alerts_dict

    def user_alerting(self):
        """Метод для оповещения пользователей"""
        d = self.user_alerts_dict
        if len(d) == 0:
            return
        for wall_id, users_list in d.items():
            for current_user in users_list:
                # Отправляем новость
                self.club_vk.method('messages.send',
                                    {'user_id': current_user, 'random_id': get_random_id(), 'attachment': wall_id})
                # +1 пост для пользователя
                self.mongo_obj.inc_user_postssend(current_user)
                time.sleep(0.2)


class UserAlertClass:
    """Класс для оповещения пользователей спустя N времени"""

    def __init__(self, token, connection_str):
        # Создаем табличку ttl и выставляем ttl для коллекции

        self.group_vk = vk_api.VkApi(token=token)

        # Соединение с БД
        self.mongo_ttl_obj = MongoTTLClass(connection_str)
        self.mongo_obj = MongoMainClass(connection_str)
        self.mongo_msg_obj = MongoMsgClass(connection_str)

        self.mongo_ttl_obj.create_ttl_table()

        while True:
            self.step12_13to14_checker()  # как новость приедет
            self.step15to16_checker()  # 2 дня
            self.step19to20_checker()  # 2 недели
            self.step22to23plus_checker()  # 1 неделя
            time.sleep(30)

    def step12_13to14_checker(self):
        all_list = self.mongo_obj.get_all_users()
        for user in all_list:
            if (user["current_step"] == 12 or user["current_step"] == 13) and user["posts_send"] > 0:
                self.step14_alter(user["user_id"])

    def step15to16_checker(self):
        """Проверка на переход от шага 15 к 16"""
        all_list = self.mongo_obj.get_all_users()
        for user in all_list:
            if user["current_step"] == 15 and self.mongo_ttl_obj.get_ttl_table(user["_id"]):
                # Отправляем сообщеньку и меняем шаг
                self.step16(user["user_id"])

    def step19to20_checker(self):
        """Проверка на переход от шага 19 к 20"""
        all_list = self.mongo_obj.get_all_users()
        for user in all_list:
            if user["current_step"] == 19 and self.mongo_ttl_obj.get_ttl_table(user["_id"]):
                # Отправляем сообщеньку и меняем шаг
                self.step20(user["user_id"])

    def step22to23plus_checker(self):
        """Проверка на переход от шага 22 к 23+ шагам"""

        wish_dict = {
            "Дать другие товары": self.step_23,
            "Понизить цены": self.step_24,
            "Повысить качество": self.step_25,
        }

        all_list = self.mongo_obj.get_all_users()
        for user in all_list:
            if user["current_step"] == 22 and self.mongo_ttl_obj.get_ttl_table(user["_id"]):
                user_wish = self.mongo_obj.get_wishbyuser(user["user_id"])
                if user_wish in wish_dict:
                    wish_dict[user_wish](user["user_id"])

    def step14_alter(self, user_id):
        """
        Альтернативная реализация шага 14
        Отличия:
        - Не выставляет priority_type от кастома
        - Обращение не через event
        """
        self.mongo_obj.update_userdata(user_id, {"current_step": 14})
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Получить купон', color=VkKeyboardColor.DEFAULT)
        message_str = self.mongo_msg_obj.get_message(14, user_id)
        self.group_vk.method('messages.send', {'user_id': user_id, 'random_id': get_random_id(), 'message': message_str,
                                               "keyboard": keyboard.get_keyboard()})

    def step16(self, user_id):
        """Обработка шага 16"""
        self.mongo_obj.update_userdata(user_id, {"current_step": 16})
        message_str = self.mongo_msg_obj.get_message(16, user_id)
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Да', color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Нет', color=VkKeyboardColor.DEFAULT)
        self.group_vk.method('messages.send', {'user_id': user_id, 'random_id': get_random_id(), 'message': message_str,
                                               "keyboard": keyboard.get_keyboard()})

    def step20(self, user_id):
        """Обработка шага 20"""
        self.mongo_obj.update_userdata(user_id, {"current_step": 20})
        message_str = self.mongo_msg_obj.get_message(20, user_id)
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Да', color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Нет', color=VkKeyboardColor.DEFAULT)
        self.group_vk.method('messages.send', {'user_id': user_id, 'random_id': get_random_id(), 'message': message_str,
                                               "keyboard": keyboard.get_keyboard()})

    def step_23(self, user_id):
        """Обработка шага 23"""
        self.mongo_obj.update_userdata(user_id, {"current_step": 23})
        message_str = self.mongo_msg_obj.get_message(23, user_id)
        self.group_vk.method('messages.send',
                             {'user_id': user_id, 'random_id': get_random_id(), 'message': message_str})

    def step_24(self, user_id):
        """Обработка шага 24"""
        self.mongo_obj.update_userdata(user_id, {"current_step": 24})
        message_str = self.mongo_msg_obj.get_message(24, user_id)
        self.group_vk.method('messages.send',
                             {'user_id': user_id, 'random_id': get_random_id(), 'message': message_str})

    def step_25(self, user_id):
        """Обработка шага 25"""
        self.mongo_obj.update_userdata(user_id, {"current_step": 25})
        message_str = self.mongo_msg_obj.get_message(25, user_id)
        self.group_vk.method('messages.send',
                             {'user_id': user_id, 'random_id': get_random_id(), 'message': message_str})


class PhotoUploaderClass:
    """Класс для загрузки фото в VK"""

    def __init__(self, vk, user_id, path):
        self.vk = vk
        self.user_id = user_id
        self.path = path
        self.__photo_str = None
        self.photo_uploader()

    @property
    def photo_str(self):
        return self.__photo_str

    def photo_uploader(self):
        """Загрузка фото с локали в VK"""

        server_url = self.vk.method('photos.getMessagesUploadServer', {
            'peer_id': self.user_id})["upload_url"]
        photo_r = requests.post(
            server_url, files={'photo': open(self.path, 'rb')}).json()
        photo_final = self.vk.method("photos.saveMessagesPhoto", {
            "photo": photo_r["photo"], "server": photo_r["server"], "hash": photo_r["hash"]})[0]
        photo_str = "photo" + \
                    str(photo_final["owner_id"]) + "_" + str(photo_final["id"])
        self.__photo_str = photo_str


class MainClass:
    def __init__(self, token, connection_str):

        # Авторизуемся как сообщество
        self.vk = vk_api.VkApi(token=token)
        # Взаимодействие с БД пользователей
        self.mongo_obj = MongoMainClass(connection_str)
        # Взаимодействие с исходящими сообщеньками в БД
        self.mongo_msg_obj = MongoMsgClass(connection_str)
        # Выставление ожидания времени ttl в табличке
        self.mongo_ttl_obj = MongoTTLClass(connection_str)

        # Сообщение и какой метод за него отвечает
        self.main_dict = {
            "Начать": self.step_1,
            "начать": self.step_1,
            "начало": self.step_1,
            "Начало": self.step_1,
            "Старт": self.step_1,
            "Магазин": self.step_2,
            "Чек-лист &quot;Трушного боббера&quot;": self.step_3,

            "Yamaha Drag Star 1100" : self.step_6,
            "Yamaha Drag Star 400/650" : self.step_6,
            "Honda Steed 400/600" : self.step_6,
            "Другая" : self.step_5,

            "Кастом": self.step_8,
            "Сток": self.step_7,
            "Раздел расходники" : self.step_12,
            "Все товары" : self.step_13, 
           
            "Дешево и сердито": self.step_11,
            "Недорогой эксклюзив": self.step_11,
            "Дорогой эксклюзив": self.step_11,
            "Дорого-богато": self.step_11,
            "Цена": self.step_14,
            "Качество": self.step_14,
            "Да": self.step_17,

            "Дать другие товары" : self.step_22,
            "Понизить цены" : self.step_22,
            "Повысить качество" : self.step_22,
            "Мне это не интересно" : self.step_22,
        }

        self.processing()

    def processing(self):
        """Обработка входящих сообщений"""
        # Работа с сообщениями
        longpoll = VkLongPoll(self.vk)

        # Основной цикл
        for event in longpoll.listen():

            # Если пришло новое сообщение
            if event.type == VkEventType.MESSAGE_NEW:

                # Если оно имеет метку для бота
                if event.to_me:

                    # Если текст есть в словаре self.main_dict, отвечающем за ассоциацию
                    if event.text in self.main_dict:
                        self.main_dict[event.text](event)

                    # Если нет, то это может быть модель мото с шага 5
                    elif self.mongo_obj.get_current_step(event.user_id) == 5:
                        self.step_6(event)

                    # Если ответ "Нет", то это либо переход к 18, либо к 21
                    elif event.text == "Нет" and self.mongo_obj.get_current_step(event.user_id) == 16:
                        self.step_18(event)
                    elif event.text == "Нет" and self.mongo_obj.get_current_step(event.user_id) == 20:
                        self.step_21(event)

                    # Если ответ "Получить купон", то это либо переход к 15, либо к 19
                    elif event.text == "Получить купон" and self.mongo_obj.get_current_step(event.user_id) == 14:
                        self.step_15(event)
                    elif event.text == "Получить купон" and self.mongo_obj.get_current_step(event.user_id) == 18:
                        self.step_19(event)

                    print("Сообщение: '{}' от https://vk.com/id{}".format(event.text, event.user_id))

    def step_1(self, event):
        """Обработка шага 1"""
        # Получаем имя пользователя
        first_name, second_name = self.get_username(event.user_id)
        if self.mongo_obj.search_userdata(event.user_id):
            # Удаление пользователя
            self.mongo_obj.remove_userdata(event.user_id)

        self.mongo_obj.new_userdata(event.user_id, first_name, second_name, 1)

        # Кнопки для VK
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Чек-лист "Трушного боббера"', color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Магазин', color=VkKeyboardColor.DEFAULT)

        # Загружаем фото
        photo_obj = PhotoUploaderClass(self.vk, event.user_id, "./img/buttons.jpg")
        message_str = self.mongo_msg_obj.get_message(1, event.user_id)
        self.vk.method('messages.send',
                       {'user_id': event.user_id, 'random_id': get_random_id(), "keyboard": keyboard.get_keyboard(),
                        'message': message_str, 'attachment': photo_obj.photo_str})

    def step_2(self, event):
        """Обработка шага 2"""
        if self.step_controller(event.user_id, 1):
            return
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 2})
        message_str = self.mongo_msg_obj.get_message(2, event.user_id)
        self.vk.method('messages.send',
                       {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})
        # Т.к. у нас безусловный переход от 2 к 4 шагу
        time.sleep(2)
        self.step_4(event)

    def step_3(self, event):
        """Обработка шага 3"""
        if self.step_controller(event.user_id, 1):
            return
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 3})
        message_str = self.mongo_msg_obj.get_message(3, event.user_id)
        self.vk.method('messages.send',
                       {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})
        # Т.к. у нас безусловный переход от 3 к 4 шагу
        time.sleep(2)
        self.step_4(event)

    def step_4(self, event):
        """
        Обработка шага 4
        - Вызывается только от step_2/step_3
        """
        if self.step_controller(event.user_id, 2, 3):
            return
        
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button("Yamaha Drag Star 1100", color=VkKeyboardColor.DEFAULT)
        keyboard.add_line()
        keyboard.add_button("Yamaha Drag Star 400/650", color=VkKeyboardColor.DEFAULT)
        keyboard.add_line()
        keyboard.add_button("Honda Steed 400/600")
        keyboard.add_line()
        keyboard.add_button("Другая")

        self.mongo_obj.update_userdata(event.user_id, {"current_step": 4})
        message_str = self.mongo_msg_obj.get_message(4, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, "keyboard": keyboard.get_keyboard()})

    def step_5(self, event):
        """
        Обработка шага 5
        Предложение о выборе модели мото
        """
        if self.step_controller(event.user_id, 4):
            return
        
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 5})
        message_str = self.mongo_msg_obj.get_message(5, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})


    def step_6(self, event):
        """
        Обработка шага 6
        Вызывается после того, как пользователь введет какой-либо текст после шага 5 или выберет button на шаге 4
        """
        if self.step_controller(event.user_id, 4, 5):
            return
        # Занесение информации о модели
        moto_model = event.text
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 6}, {"moto_model": moto_model})
        # Кнопки для VK
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Кастом', color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Сток', color=VkKeyboardColor.DEFAULT)
        message_str = self.mongo_msg_obj.get_message(6, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, "keyboard": keyboard.get_keyboard()})

    def step_7(self, event):
        """Обработка шага 7"""
        if self.step_controller(event.user_id, 6):
            return
        
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Раздел Расходники', color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Все товары', color=VkKeyboardColor.DEFAULT)
        self.mongo_obj.update_userdata(event.user_id, {"moto_type": "сток"}, {"current_step": 7})
        message_str = self.mongo_msg_obj.get_message(7, event.user_id)
        photo_obj = PhotoUploaderClass(self.vk, event.user_id, "./img/expendable.jpg")
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str,
                                         'attachment': photo_obj.photo_str, "keyboard": keyboard.get_keyboard()})

    def step_8(self, event):
        """Обработка шага 8"""
        if self.step_controller(event.user_id, 6):
            return
        self.mongo_obj.update_userdata(event.user_id, {"moto_type": "кастом"}, {"current_step": 8})
        message_str = self.mongo_msg_obj.get_message(8, event.user_id)
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Раздел товаров кастом', color=VkKeyboardColor.DEFAULT)
        photo_obj = PhotoUploaderClass(self.vk, event.user_id, "./img/custom.jpg")
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str,
                                         'attachment': photo_obj.photo_str, "keyboard": keyboard.get_keyboard()})
        time.sleep(2)
        self.step_8(event)

    def step_9(self, event):
        """Обработка шага 9"""
        if self.step_controller(event.user_id, 8):
            return
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 9})
        message_str = self.mongo_msg_obj.get_message(9, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})
        time.sleep(1)
        self.step_10(event)

    def step_10(self, event):
        """Обработка шага 10"""
        if self.step_controller(event.user_id, 9):
            return
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 10})
        # Кнопки для VK
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Дешево и сердито', color=VkKeyboardColor.DEFAULT)
        keyboard.add_line()
        keyboard.add_button('Недорогой эксклюзив', color=VkKeyboardColor.DEFAULT)
        keyboard.add_line()
        keyboard.add_button('Дорогой эксклюзив', color=VkKeyboardColor.DEFAULT)
        keyboard.add_line()
        keyboard.add_button('Дорого-богато', color=VkKeyboardColor.DEFAULT)
        message_str = self.mongo_msg_obj.get_message(10, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str,"keyboard": keyboard.get_keyboard()})

    def step_11(self, event):
        """Обработка шага 11"""
        if self.step_controller(event.user_id, 10):
            return
        # Занесение информации о типе платежеспособности пользователя
        price_type = event.text
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 11}, {"price_type": price_type})
        # Кнопки для VK
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Цена', color=VkKeyboardColor.DEFAULT)
        keyboard.add_button('Качество', color=VkKeyboardColor.DEFAULT)

        message_str = self.mongo_msg_obj.get_message(11, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str,
                                         "keyboard": keyboard.get_keyboard()})

    def step_12(self, event):
        """Обработка шага 12"""
        if self.step_controller(event.user_id, 7):
            return
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 12})
        message_str = self.mongo_msg_obj.get_message(12, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str,})

    def step_13(self, event):
        """Обработка шага 13"""
        if self.step_controller(event.user_id, 7):
            return
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 13})
        message_str = self.mongo_msg_obj.get_message(13, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str,})

    def step_14(self, event):
        """Обработка шага 14"""
        if self.step_controller(event.user_id, 11):
            return
        # Занесение информации о приоритетах пользователя
        priority_type = event.text
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 14}, {"priority_type": priority_type})
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Получить купон', color=VkKeyboardColor.DEFAULT)
        message_str = self.mongo_msg_obj.get_message(14, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str, "keyboard": keyboard.get_keyboard()})

    def step_15(self, event):
        """Обработка шага 15"""
        if self.step_controller(event.user_id, 14):
            return
        message_str = self.mongo_msg_obj.get_message(15, event.user_id)
        photo_obj = PhotoUploaderClass(self.vk, event.user_id, "./img/coupon_5.jpg")
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str,
                                         'attachment': photo_obj.photo_str})

        # TODO Выставляем TTL для step15to16
        self.mongo_ttl_obj.set_ttl_table("step15to16", event.user_id)
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 15}, {"coupon_5": "seen"})

    def step_17(self, event):
        """Обработка шага 17"""
        if self.step_controller(event.user_id, 16, 20):
            return
        if self.mongo_obj.get_current_step(event.user_id) == 20:
            self.mongo_obj.update_userdata(event.user_id, {"current_step": 17}, {"coupon_10": "true"})
        else:
            self.mongo_obj.update_userdata(event.user_id, {"current_step": 17}, {"coupon_5": "true"})
        message_str = self.mongo_msg_obj.get_message(17, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})

    def step_18(self, event):
        """Обработка шага 18"""
        if self.step_controller(event.user_id, 16):
            return
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 18}, {"coupon_5": "false"})
        message_str = self.mongo_msg_obj.get_message(18, event.user_id)
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Получить купон', color=VkKeyboardColor.DEFAULT)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str,
                                         "keyboard": keyboard.get_keyboard()})

    def step_19(self, event):
        """Обработка шага 19"""
        if self.step_controller(event.user_id, 18):
            return
        message_str = self.mongo_msg_obj.get_message(19, event.user_id)
        photo_obj = PhotoUploaderClass(self.vk, event.user_id, "./img/coupon_10.jpg")
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str,
                                         'attachment': photo_obj.photo_str})

        # TODO Выставляем TTL для step19to20
        self.mongo_ttl_obj.set_ttl_table("step19to20", event.user_id)
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 19}, {"coupon_10": "seen"})

    def step_21(self, event):
        """Обработка шага 21"""
        if self.step_controller(event.user_id, 20):
            return
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 21}, {"coupon_10": "false"})
        message_str = self.mongo_msg_obj.get_message(21, event.user_id)
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('Дать другие товары', color=VkKeyboardColor.DEFAULT)
        keyboard.add_line()
        keyboard.add_button('Понизить цены', color=VkKeyboardColor.DEFAULT)
        keyboard.add_line()
        keyboard.add_button('Повысить качество', color=VkKeyboardColor.DEFAULT)
        keyboard.add_line()
        keyboard.add_button('Мне это не интересно', color=VkKeyboardColor.DEFAULT)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str,
                                         "keyboard": keyboard.get_keyboard()})

    def step_22(self, event):
        """Обработка шага 22"""
        if self.step_controller(event.user_id, 18):
            return
        wish = event.text
        message_str = self.mongo_msg_obj.get_message(22, event.user_id)
        self.vk.method('messages.send', {'user_id': event.user_id, 'random_id': get_random_id(), 'message': message_str})

        # Выставляем TTL для step19to20
        self.mongo_ttl_obj.set_ttl_table("step22to23plus", event.user_id)
        self.mongo_obj.update_userdata(event.user_id, {"current_step": 22}, {"wish": wish})

    def get_username(self, user_id):
        """Метод, возвращающий имя пользователя по id"""
        name = self.vk.method('users.get', {'user_id': user_id})[0]
        return name["first_name"], name["last_name"]

    def step_controller(self, user_id, *ids):
        """Метод для контроля перехода шагов"""
        detect_flag = True
        for id_ in ids:
            if self.mongo_obj.get_current_step(user_id) == id_:
                detect_flag = False
        return detect_flag


if __name__ == "__main__":
    p_list = []
    settings = util_module.get_settings()
    p = mp.Process(target=WallMonitoringClass, args=(
        settings["user_token"], settings["group_token"], settings["group_id"], settings["mongodb_connection"],))
    p_list.append(p)
    p = mp.Process(target=MainClass, args=(settings["group_token"], settings["mongodb_connection"],))
    p_list.append(p)
    p = mp.Process(target=UserAlertClass, args=(settings["group_token"], settings["mongodb_connection"],))
    p_list.append(p)
    for p in p_list:
        p.start()

    # Ультракостыль, чтоб Docker в случае ошибки перезапускал скрипт
    stop_flag = True
    while stop_flag:
        for proc in p_list:
            if type(proc.exitcode) == int:
                print('MAIN остановил работу!')
                stop_flag = False
        time.sleep(0.1)

    for proc in p_list:
        proc.terminate()
