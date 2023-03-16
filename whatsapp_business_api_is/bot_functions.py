from whatsapp_business_api_is.utils import set_data


class Functions:

    @staticmethod
    def do_nothing(*args, **kwargs):
        pass

    @staticmethod
    def save_data(user, msg, msg_obj=None, data=None):
        try:
            set_data(user, data, msg)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f" Failed to save data: {e}")

    @staticmethod
    def get_current_user(user, msg, msg_obj=None, data=None):
        return user
