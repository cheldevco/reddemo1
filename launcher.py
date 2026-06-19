import os
import json
import threading
import requests
import subprocess
import customtkinter as cctk

# Настройка тёмной темы
cctk.set_appearance_mode("Dark")

CONFIG_FILE = "launcher_config.json"

class RedDemoLauncher(cctk.CTk):
    def __init__(self, supabase_client):
        super().__init__()
        
        self.supabase = supabase_client
        self.current_user = None
        self.user_profile = {}
        self.games_list = []
        self.is_downloading = False
        
        # Настройки валюты по умолчанию
        self.current_currency = "RUB"
        self.currency_symbols = {"RUB": "руб.", "KZT": "тг.", "USD": "$"}
        self.currency_rates = {"RUB": 1.0, "KZT": 4.9, "USD": 0.011} # Примерный курс для тестов

        # Элементы интерфейса для загрузки
        self.active_progress_bar = None
        self.active_status_label = None

        # Конфигурация окна (горизонтальный дизайн требует больше ширины)
        self.title("RedDemo Launcher")
        self.geometry("1100x680")
        self.resizable(False, False)

        # Проверяем авто-вход
        self.check_auto_login()

    # ==========================================
    # ЛОГИКА АВТО-ВХОДА И КЭША
    # ==========================================
    def check_auto_login(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                email = config.get("email")
                password = config.get("password")
                if email and password:
                    print(f"[AUTO-LOGIN] Пробуем войти в аккаунт: {email}")
                    res = self.supabase.auth.sign_in_with_password({"email": email, "password": password})
                    if res.user:
                        self.current_user = res.user
                        self.load_launcher_data()
                        return
            except Exception as e:
                print(f"[AUTO-LOGIN] Ошибка авто-входа: {e}")
        
        # Если авто-вход не сработал или нет конфига, показываем форму входа
        self.build_auth_layout()

    def save_credentials(self, email, password):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"email": email, "password": password}, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[CONFIG ERROR] Не удалось сохранить кэш входа: {e}")

    # ==========================================
    # ИНТЕРФЕЙС: ВХОД И РЕГИСТРАЦИЯ
    # ==========================================
    def build_auth_layout(self, is_register=False):
        self.clear_all_widgets()
        self.configure(fg_color="#1a0f0f") # Тёмно-бордовый фон всего окна

        self.auth_frame = cctk.CTkFrame(self, width=380, height=460, corner_radius=8, fg_color="#2b1616")
        self.auth_frame.place(relx=0.5, rely=0.5, anchor="center")

        title_text = "РЕГИСТРАЦИЯ" if is_register else "ВХОД В АККАУНТ"
        title = cctk.CTkLabel(self.auth_frame, text=title_text, font=cctk.CTkFont(size=22, weight="bold"), text_color="#ff4d4d")
        title.pack(pady=(35, 20))

        self.entry_email = cctk.CTkEntry(self.auth_frame, width=290, height=40, placeholder_text="Email", fg_color="#421f1f", text_color="#fff", border_width=1, border_color="#802b2b")
        self.entry_email.pack(pady=10)

        self.entry_password = cctk.CTkEntry(self.auth_frame, width=290, height=40, placeholder_text="Пароль", show="*", fg_color="#421f1f", text_color="#fff", border_width=1, border_color="#802b2b")
        self.entry_password.pack(pady=10)

        self.error_label = cctk.CTkLabel(self.auth_frame, text="", text_color="#ff6666", font=cctk.CTkFont(size=13))
        self.error_label.pack(pady=5)

        if is_register:
            btn_action = cctk.CTkButton(self.auth_frame, text="Создать аккаунт", width=290, height=45, fg_color="#992222", hover_color="#cc3333", text_color="#fff", font=cctk.CTkFont(size=15, weight="bold"), command=self.process_register)
            btn_action.pack(pady=10)
            
            btn_toggle = cctk.CTkButton(self.auth_frame, text="Уже есть аккаунт? Войти", fg_color="transparent", text_color="#ff9999", hover=False, command=lambda: self.build_auth_layout(False))
            btn_toggle.pack()
        else:
            btn_action = cctk.CTkButton(self.auth_frame, text="Войти", width=290, height=45, fg_color="#992222", hover_color="#cc3333", text_color="#fff", font=cctk.CTkFont(size=15, weight="bold"), command=self.process_login)
            btn_action.pack(pady=10)
            
            btn_toggle = cctk.CTkButton(self.auth_frame, text="Нет аккаунта? Зарегистрироваться", fg_color="transparent", text_color="#ff9999", hover=False, command=lambda: self.build_auth_layout(True))
            btn_toggle.pack()

    def process_login(self):
        email = self.entry_email.get().strip()
        password = self.entry_password.get().strip()
        if not email or not password:
            self.error_label.configure(text="Заполните все поля!")
            return
        try:
            res = self.supabase.auth.sign_in_with_password({"email": email, "password": password})
            if res.user:
                self.current_user = res.user
                self.save_credentials(email, password)
                self.load_launcher_data()
        except Exception:
            self.error_label.configure(text="Неверный логин или пароль")

    def process_register(self):
        email = self.entry_email.get().strip()
        password = self.entry_password.get().strip()
        if not email or not password:
            self.error_label.configure(text="Заполните все поля!")
            return
        if len(password) < 6:
            self.error_label.configure(text="Пароль должен быть от 6 символов!")
            return
        try:
            res = self.supabase.auth.sign_up({"email": email, "password": password})
            if res.user:
                # Создаем пустую запись профиля в таблице profiles
                self.supabase.table("profiles").insert({"id": res.user.id, "balance": 0, "owned_games": []}).execute()
                self.error_label.configure(text="Успешно! Теперь войдите.", text_color="#55ff55")
        except Exception as e:
            self.error_label.configure(text="Ошибка регистрации или email занят")

    # ==========================================
    # ЗАГРУЗКА ДАННЫХ
    # ==========================================
    def load_launcher_data(self):
        if self.current_user:
            try:
                prof_res = self.supabase.table("profiles").select("*").eq("id", self.current_user.id).single().execute()
                if prof_res.data:
                    self.user_profile = prof_res.data
                    og = self.user_profile.get("owned_games", [])
                    if isinstance(og, str):
                        clean_og = og.replace("{","").replace("}","").replace("[","").replace("]","")
                        self.user_profile["owned_games"] = [int(x) for x in clean_og.split(",") if x.strip()]
                    elif isinstance(og, list):
                        self.user_profile["owned_games"] = [int(x) for x in og]
            except Exception as e:
                print(f"[DATA ERROR] Не удалось загрузить профиль: {e}")
                self.user_profile = {"balance": 0, "owned_games": []}

        try:
            games_res = self.supabase.table("games").select("*").execute()
            if games_res.data:
                self.games_list = games_res.data
                with open("games_cache.json", "w", encoding="utf-8") as f:
                    json.dump(self.games_list, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[DATA WARNING] Сеть недоступна, работаем через кэш: {e}")
            if os.path.exists("games_cache.json"):
                with open("games_cache.json", "r", encoding="utf-8") as f:
                    self.games_list = json.load(f)

        self.clear_all_widgets()
        self.build_main_layout()

    # ==========================================
    # ИНТЕРФЕЙС RED.DEMO (ГОРИЗОНТАЛЬНЫЙ КРАСНЫЙ)
    # ==========================================
    def build_main_layout(self):
        self.configure(fg_color="#1a0f0f")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0) # Верхняя панель меню
        self.rowconfigure(1, weight=1) # Основной контент

        # --- ГОРИЗОНТАЛЬНАЯ ВЕРХНЯЯ ПАНЕЛЬ ---
        self.top_bar = cctk.CTkFrame(self, height=65, corner_radius=0, fg_color="#2b1616", border_width=1, border_color="#421f1f")
        self.top_bar.grid(row=0, column=0, sticky="ew")
        self.top_bar.pack_propagate(False)

        logo = cctk.CTkLabel(self.top_bar, text="RED.DEMO", font=cctk.CTkFont(size=20, weight="bold"), text_color="#ff4d4d")
        logo.pack(side="left", padx=25)

        self.btn_store = cctk.CTkButton(self.top_bar, text="МАГАЗИН", fg_color="#421f1f", text_color="#ff9999", width=110, height=35, font=cctk.CTkFont(size=13, weight="bold"), command=self.switch_to_store)
        self.btn_store.pack(side="left", padx=10)

        self.btn_library = cctk.CTkButton(self.top_bar, text="БИБЛИОТЕКА", fg_color="transparent", text_color="#b8b6b4", width=110, height=35, font=cctk.CTkFont(size=13, weight="bold"), command=self.switch_to_library)
        self.btn_library.pack(side="left", padx=10)

        # Правая часть верхней панели (Профиль, Валюта, Код активации)
        right_box = cctk.CTkFrame(self.top_bar, fg_color="transparent")
        right_box.pack(side="right", padx=20, fill="y")

        # Переключатель валюты
        self.currency_combo = cctk.CTkComboBox(right_box, values=["RUB", "KZT", "USD"], width=75, height=28, fg_color="#421f1f", button_color="#661a1a", border_width=0, command=self.change_currency)
        self.currency_combo.set(self.current_currency)
        self.currency_combo.pack(side="left", padx=10, pady=18)

        # Кнопка Активации кода
        btn_promo = cctk.CTkButton(right_box, text="Активировать код", fg_color="#5e1414", hover_color="#801a1a", width=130, height=28, font=cctk.CTkFont(size=11, weight="bold"), command=self.open_activation_dialog)
        btn_promo.pack(side="left", padx=10, pady=18)

        # Баланс и Юзер
        user_email = self.current_user.email if self.current_user else "GUEST"
        self.lbl_user_info = cctk.CTkLabel(right_box, text=f"{user_email.split('@')[0].upper()} ({self.get_formatted_balance()})", font=cctk.CTkFont(size=13, weight="bold"), text_color="#ff9999")
        self.lbl_user_info.pack(side="left", padx=15)

        # Контентная зона под верхним меню
        self.content_area = cctk.CTkScrollableFrame(self, fg_color="#1f1212", corner_radius=0)
        self.content_area.grid(row=1, column=0, sticky="nsew")

        self.switch_to_store()

    # ==========================================
    # РАСЧЕТ И ОБНОВЛЕНИЕ ВАЛЮТЫ
    # ==========================================
    def change_currency(self, choice):
        self.current_currency = choice
        self.update_balance_display()
        if self.btn_store.cget("fg_color") != "transparent":
            self.switch_to_store()

    def get_formatted_balance(self):
        base_rub = self.user_profile.get("balance", 0)
        converted = round(base_rub * self.currency_rates[self.current_currency], 2)
        if self.current_currency == "RUB": converted = int(base_rub)
        return f"{converted} {self.currency_symbols[self.current_currency]}"

    def update_balance_display(self):
        if hasattr(self, 'lbl_user_info') and self.lbl_user_info.winfo_exists():
            user_email = self.current_user.email if self.current_user else "GUEST"
            self.lbl_user_info.configure(text=f"{user_email.split('@')[0].upper()} ({self.get_formatted_balance()})")

    # ==========================================
    # ЛОГИКА КОДОВ АКТИВАЦИИ
    # ==========================================
    def open_activation_dialog(self):
        dialog = cctk.CTkInputDialog(text="Введите промокод на баланс или игру:", title="Активация ключа")
        code = dialog.get_input()
        if code:
            self.process_activation_code(code.strip())

    def process_activation_code(self, code):
        try:
            res = self.supabase.table("promo_codes").select("*").eq("code", code).eq("used", False).execute()
            if res.data:
                promo = res.data[0]
                reward_type = promo.get("type") 
                reward_value = promo.get("value") 

                if reward_type == "balance":
                    new_balance = self.user_profile.get("balance", 0) + float(reward_value)
                    self.supabase.table("profiles").update({"balance": new_balance}).eq("id", self.current_user.id).execute()
                    self.user_profile["balance"] = new_balance
                    print("[PROMO] Код на баланс успешно зачислен!")
                
                elif reward_type == "game":
                    game_id = int(reward_value)
                    updated_owned = list(self.user_profile.get("owned_games", []))
                    if game_id not in updated_owned:
                        updated_owned.append(game_id)
                    self.supabase.table("profiles").update({"owned_games": updated_owned}).eq("id", self.current_user.id).execute()
                    self.user_profile["owned_games"] = updated_owned
                    print("[PROMO] Игра активирована в библиотеку!")

                self.supabase.table("promo_codes").update({"used": True}).eq("id", promo.get("id")).execute()
                self.update_balance_display()
                
                if self.btn_library.cget("fg_color") != "transparent":
                    self.switch_to_library()
                else:
                    self.switch_to_store()
            else:
                print("[PROMO] Неверный или уже использованный промокод.")
        except Exception as e:
            print(f"[PROMO ERROR] Не удалось обработать код: {e}")

    # ==========================================
    # СТРАНИЦА: МАГАЗИН ИГР
    # ==========================================
    def switch_to_store(self):
        self.clear_content_area()
        self.btn_store.configure(fg_color="#421f1f", text_color="#ff9999")
        self.btn_library.configure(fg_color="transparent", text_color="#b8b6b4")

        title = cctk.CTkLabel(self.content_area, text="МАГАЗИН ИГР", font=cctk.CTkFont(size=18, weight="bold"), text_color="#ff9999")
        title.pack(padx=25, pady=(20, 10), anchor="w")

        owned_games = self.user_profile.get("owned_games", [])

        for game in self.games_list:
            if game.get("id") in owned_games: continue

            item = cctk.CTkFrame(self.content_area, fg_color="#2b1616", height=75, corner_radius=4, border_width=1, border_color="#3d1d1d")
            item.pack(padx=25, pady=6, fill="x")
            item.pack_propagate(False)

            lbl_name = cctk.CTkLabel(item, text=game.get("name") or "Игра", font=cctk.CTkFont(size=15, weight="bold"), text_color="#fff")
            lbl_name.pack(side="left", padx=20)

            price_rub = game.get("price", 0)
            price_converted = round(price_rub * self.currency_rates[self.current_currency], 2)
            if self.current_currency == "RUB": price_converted = int(price_rub)
            
            price_text = f"{price_converted} {self.currency_symbols[self.current_currency]}"

            btn_buy = cctk.CTkButton(item, text=price_text, fg_color="#992222", hover_color="#cc3333", text_color="#fff", width=120, height=34, font=cctk.CTkFont(size=13, weight="bold"), command=lambda g=game: self.purchase_game(g))
            btn_buy.pack(side="right", padx=20)

    # ==========================================
    # СТРАНИЦА: БИБЛИОТЕКА ИГР
    # ==========================================
    def switch_to_library(self):
        self.clear_content_area()
        self.btn_store.configure(fg_color="transparent", text_color="#b8b6b4")
        self.btn_library.configure(fg_color="#421f1f", text_color="#ff9999")

        title = cctk.CTkLabel(self.content_area, text="БИБЛИОТЕКА ИГР", font=cctk.CTkFont(size=18, weight="bold"), text_color="#ff9999")
        title.pack(padx=25, pady=(20, 10), anchor="w")

        owned_games = self.user_profile.get("owned_games", [])

        for game in self.games_list:
            if game.get("id") not in owned_games: continue

            game_name = game.get("name") or "Игра"
            launch_path_from_db = game.get("launch_exe", "null")
            
            item = cctk.CTkFrame(self.content_area, fg_color="#2b1616", height=85, corner_radius=4, border_width=1, border_color="#3d1d1d")
            item.pack(padx=25, pady=6, fill="x")
            item.pack_propagate(False)

            info_block = cctk.CTkFrame(item, fg_color="transparent")
            info_block.pack(side="left", padx=20, fill="y", pady=10)

            lbl_name = cctk.CTkLabel(info_block, text=game_name, font=cctk.CTkFont(size=15, weight="bold"), text_color="#fff", anchor="w")
            lbl_name.pack(anchor="w")

            lbl_status = cctk.CTkLabel(info_block, text="Не установлена", font=cctk.CTkFont(size=12), text_color="#aaa", anchor="w")
            lbl_status.pack(anchor="w")

            p_bar = cctk.CTkProgressBar(item, width=180, height=8, fg_color="#421f1f", progress_color="#ff4d4d")
            p_bar.set(0)

            game_dir = os.path.join(os.getcwd(), "Games", game_name)
            btn_action = cctk.CTkButton(item, text="УСТАНОВИТЬ", fg_color="#421f1f", hover_color="#5e2929", text_color="#fff", width=110, height=34, font=cctk.CTkFont(size=12, weight="bold"))
            
            if os.path.exists(game_dir) and not self.is_downloading:
                lbl_status.configure(text="Готова к запуску", text_color="#ff4d4d")
                btn_action.configure(text="ИГРАТЬ", fg_color="#992222", hover_color="#cc3333", 
                                     command=lambda gd=game_dir, lp=launch_path_from_db: self.launch_game(gd, lp))
            else:
                btn_action.configure(command=lambda g=game, b=btn_action, p=p_bar, l=lbl_status: self.start_download(g, b, p, l))

            btn_action.pack(side="right", padx=20)
            p_bar.pack(side="right", padx=20)
            p_bar.pack_forget()

    # ==========================================
    # ЛОГИКА ПОКУПКИ
    # ==========================================
    def purchase_game(self, game):
        game_id = game.get("id")
        price = game.get("price", 0)
        current_balance = self.user_profile.get("balance", 0)

        if current_balance < price:
            print("Недостаточно средств на балансе!")
            return

        updated_owned = list(self.user_profile.get("owned_games", []))
        if game_id not in updated_owned: updated_owned.append(game_id)
        new_balance = current_balance - price

        try:
            self.supabase.table("profiles").update({"balance": new_balance, "owned_games": updated_owned}).eq("id", self.current_user.id).execute()
            self.user_profile["balance"] = new_balance
            self.user_profile["owned_games"] = updated_owned
            self.update_balance_display()
            self.switch_to_store()
        except Exception as e:
            print(f"Ошибка покупки: {e}")

    # ==========================================
    # ПОТОКОВОЕ СКАЧИВАНИЕ И РАСПАКОВКА
    # ==========================================
    def start_download(self, game, button, progress_bar, status_label):
        if self.is_downloading: return
        self.active_progress_bar = progress_bar
        self.active_status_label = status_label
        button.configure(state="disabled", text="СКАЧИВАНИЕ...")
        self.active_progress_bar.pack(side="right", padx=20)
        threading.Thread(target=self.download_game_worker, args=(game, button), daemon=True).start()

    def download_game_worker(self, game, button):
        self.is_downloading = True
        game_name = game.get("name") or "Unknown_Game"
        url = game.get("download_url") or game.get("url")
        
        if not url:
            self.active_status_label.configure(text="Нет ссылки!", text_color="#ff3333")
            self.is_downloading = False
            return

        # Защищенная проверка Google Диска: если нет явного .zip в ссылке, значит считаем расширением .7z
        ext = ".zip" if ".zip" in url.lower() else ".7z"
        install_dir = os.path.join(os.getcwd(), "Games", game_name)
        os.makedirs(install_dir, exist_ok=True)
        archive_path = os.path.join(install_dir, f"{game_name}{ext}")
        
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            
            with open(archive_path, "wb") as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = downloaded / total_size
                            self.active_progress_bar.set(percent)
                            self.active_status_label.configure(text=f"{round(downloaded/(1024*1024),1)}MB / {round(total_size/(1024*1024),1)}MB")

            self.active_status_label.configure(text="Распаковка файлов...", text_color="#ff9999")
            
            if ext == ".7z":
                exe_7za = os.path.join(os.getcwd(), "7za.exe")
                if os.path.exists(exe_7za):
                    cmd = f'"{exe_7za}" x "{archive_path}" -o"{install_dir}" -y'
                    unpack_success = (subprocess.run(cmd, shell=True).returncode == 0)
                else: 
                    print("[ERROR] 7za.exe не найден в корне!")
                    unpack_success = False
            else:
                import zipfile
                with zipfile.ZipFile(archive_path, 'r') as archive:
                    archive.extractall(path=install_dir)
                unpack_success = True

            if unpack_success:
                if os.path.exists(archive_path): os.remove(archive_path)
                self.active_status_label.configure(text="Готова к запуску", text_color="#ff4d4d")
                self.active_progress_bar.pack_forget()
                
                launch_path_from_db = game.get("launch_exe", "null")
                button.configure(state="normal", text="ИГРАТЬ", fg_color="#992222", hover_color="#cc3333", command=lambda gd=install_dir, lp=launch_path_from_db: self.launch_game(gd, lp))
            else:
                self.active_status_label.configure(text="Ошибка извлечения", text_color="#ff3333")
                button.configure(state="normal", text="ПОВТОРИТЬ")
        except Exception:
            self.active_status_label.configure(text="Ошибка сети", text_color="#ff3333")
            button.configure(state="normal", text="ПОВТОРИТЬ")
        finally:
            self.is_downloading = False

    # ==========================================
    # СИСТЕМА ЗАПУСКА ИГРЫ
    # ==========================================
    def launch_game(self, game_directory, launch_relative_path):
        if not launch_relative_path or launch_relative_path == "null":
            executable_path = None
            for root, dirs, files in os.walk(game_directory):
                for file in files:
                    if file.lower() in ["far cry 1.bat", "farcry.exe", "run.bat", "farcry2.exe"]:
                        executable_path = os.path.join(root, file)
                        break
                if executable_path: break
        else:
            games_root = os.path.dirname(game_directory)
            executable_path = os.path.normpath(os.path.join(games_root, launch_relative_path))

        if executable_path and os.path.exists(executable_path):
            print(f"[LAUNCH] Открытие файла: {executable_path}")
            working_dir = os.path.dirname(executable_path)
            subprocess.Popen(f'"{executable_path}"', cwd=working_dir, shell=True)
        else:
            print(f"[LAUNCH ERROR] Не найден файл по пути: {executable_path}")

    def clear_content_area(self):
        if hasattr(self, 'content_area') and self.content_area.winfo_exists():
            for widget in self.content_area.winfo_children(): widget.destroy()

    def clear_all_widgets(self):
        for widget in self.winfo_children(): widget.destroy()


# ==========================================
# ТОЧКА ВХОДА И КЛЮЧИ ПОДКЛЮЧЕНИЯ
# ==========================================
if __name__ == "__main__":
    from supabase import create_client, Client
    
    # Твои актуальные рабочие ключи из Supabase
    SUPABASE_URL = "https://bayqqmzeulrlrxavnbhh.supabase.co"
    SUPABASE_KEY = "sb_publishable_8XiZLsKl6Zs87BAyhCaUJw_E1fmp8S1"
    
    try:
        print("[LAUNCHER START] Авторизация и подключение к базе данных...")
        supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Создание и запуск приложения
        app = RedDemoLauncher(supabase_client)
        print("[LAUNCHER START] Окно успешно запущено.")
        app.mainloop()
        
    except Exception as init_error:
        print(f"[CRITICAL ERROR] Не удалось инициализировать лаунчер: {init_error}")
        input("\nНажмите Enter для закрытия консоли...")