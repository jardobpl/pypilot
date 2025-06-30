import os
import sys
import json
import logging
import subprocess
import webbrowser
import datetime
import re
import textwrap
import math
import locale

# Pamiętaj, aby zainstalować tę bibliotekę: pip install pyperclip
try:
    import pyperclip
except ImportError:
    print("BŁĄD: Biblioteka 'pyperclip' nie jest zainstalowana. Uruchom 'pip install pyperclip' w konsoli.")
    sys.exit(1)

# --- Stałe i Konfiguracja ---
LOG_FILE = 'log.log'
MAX_MISTAKES = 5

# Kody kolorów
COLOR_A, COLOR_B = '\033[97m', '\033[90m'
COLOR_ERROR, COLOR_PROMPT = '\033[91m', '\033[96m'
COLOR_SHORTCUT, COLOR_SUCCESS = '\033[33m', '\033[92m'
COLOR_INFO = '\033[94m'
COLOR_RESET = '\033[0m'

try:
    locale.setlocale(locale.LC_TIME, 'pl_PL.UTF-8')
except locale.Error:
    try: locale.setlocale(locale.LC_TIME, 'Polish_Poland.1250')
    except locale.Error: print("Ostrzeżenie: Nie udało się ustawić polskiej lokalizacji dla dat.")

# --- Funkcje Inicjalizacyjne i Pomocnicze ---

def setup_logging():
    """Konfiguruje system logowania do zapisywania w pliku."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename=LOG_FILE,
        filemode='a'
    )

def enable_ansi_colors():
    """Włącza obsługę kolorów ANSI w konsoli Windows."""
    if sys.platform == 'win32':
        os.system('')

def load_and_validate_config(filename: str) -> list | None:
    """Wczytuje i waliduje plik konfiguracyjny JSON."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        error_msg = f"BŁĄD: Plik konfiguracyjny '{filename}' nie został znaleziony."
        logging.error(error_msg)
        print(f"{COLOR_ERROR}{error_msg}{COLOR_RESET}")
        return None
    except json.JSONDecodeError:
        error_msg = f"BŁĄD: Plik '{filename}' zawiera błędy składni JSON."
        logging.error(error_msg)
        print(f"{COLOR_ERROR}{error_msg}{COLOR_RESET}")
        return None

    seen_numbers, seen_shortcuts = set(), set()
    for i, item in enumerate(data, 1):
        if 'numer' not in item or not isinstance(item.get('numer'), int):
            error_msg = f"BŁĄD: Pozycja nr {i} w pliku '{filename}' nie ma klucza 'numer' lub jego wartość nie jest liczbą."
            logging.error(error_msg)
            print(f"{COLOR_ERROR}{error_msg}{COLOR_RESET}")
            return None
        number = item['numer']
        if number in seen_numbers:
            error_msg = f"BŁĄD: Numer '{number}' jest zduplikowany w pliku '{filename}'."
            logging.error(error_msg)
            print(f"{COLOR_ERROR}{error_msg}{COLOR_RESET}")
            return None
        seen_numbers.add(number)
        if 'skroty' in item:
            shortcut = item['skroty']
            if not isinstance(shortcut, str) or not shortcut:
                error_msg = f"BŁĄD: 'skroty' dla pozycji z numerem {number} musi być niepustym tekstem."
                logging.error(error_msg)
                print(f"{COLOR_ERROR}{error_msg}{COLOR_RESET}")
                return None
            if shortcut in seen_shortcuts:
                error_msg = f"BŁĄD: Skrót '{shortcut}' jest zduplikowany w pliku '{filename}'."
                logging.error(error_msg)
                print(f"{COLOR_ERROR}{error_msg}{COLOR_RESET}")
                return None
            seen_shortcuts.add(shortcut)
    return data

def slugify(text: str) -> str:
    polish_map = str.maketrans('ąćęłńóśźżĄĆĘŁŃÓŚŹŻ', 'acelnoszzACELNOSZZ')
    text = text.translate(polish_map)
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text

def format_sql(sql: str) -> str:
    keywords = [
        'select', 'from', 'where', 'and', 'or', 'join', 'left join', 'right join',
        'inner join', 'outer join', 'on', 'group by', 'order by', 'limit', 'offset',
        'as', 'distinct', 'having', 'union', 'insert into', 'values', 'update', 'set',
        'delete from', 'like', 'desc', 'asc', 'in', 'not', 'exists', 'between', 'case',
        'when', 'then', 'else', 'end', 'is', 'null'
    ]
    sql = re.sub(r'\s+', ' ', sql.strip())
    for kw in sorted(keywords, key=len, reverse=True):
        pattern = r'\b' + re.escape(kw) + r'\b'
        sql = re.sub(pattern, kw.upper(), sql, flags=re.IGNORECASE)
    sql = re.sub(r'\b(FROM|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT|OFFSET|SET|VALUES|ON|JOIN|INNER JOIN|LEFT JOIN|RIGHT JOIN|OUTER JOIN)\b', r'\n\1', sql)
    sql = re.sub(r'\n(ON|JOIN|INNER JOIN|LEFT JOIN|RIGHT JOIN|OUTER JOIN)', r'\n  \1', sql)
    return sql.strip()

def process_global_commands(choice_str: str) -> str | None:
    choice = choice_str.lower()
    if choice == '>e': return 'exit'
    if choice == '>p': return 'launcher'
    if choice == '>t': return 'transform'
    if choice == '>c': return 'calculator'
    if choice == '>d': return 'date'
    return None

# --- Funkcje dla poszczególnych trybów ---

def run_launcher_mode(config: list) -> str:
    print(f"\n{COLOR_INFO}--- Menu Główne (Programy) ---{COLOR_RESET}")
    for i, item in enumerate(config):
        color = COLOR_A if i % 2 == 0 else COLOR_B
        shortcut_display = f" {COLOR_SHORTCUT}[{item['skroty']}]{color}" if 'skroty' in item else ""
        print(f"  {color}{item['numer']}. {item['name']}{shortcut_display}{COLOR_RESET}")
    mistake_counter = 0
    while mistake_counter < MAX_MISTAKES:
        prompt_text = f"\n{COLOR_PROMPT}Wybór (>p, >t, >c, >d, >e): {COLOR_RESET}"
        choice_str = input(prompt_text)
        new_mode = process_global_commands(choice_str)
        if new_mode: return new_mode
        chosen_action = None
        if choice_str:
            try:
                chosen_action = next(item for item in config if item['numer'] == int(choice_str))
            except (ValueError, StopIteration):
                chosen_action = next((item for item in config if item.get('skroty') == choice_str), None)
        if chosen_action:
            execute_action(chosen_action)
            return 'exit'
        else:
            mistake_counter += 1
            remaining = MAX_MISTAKES - mistake_counter
            logging.warning(f"Błąd wyboru: '{choice_str}'. Pomyłka nr {mistake_counter}.")
            if remaining > 0: print(f"{COLOR_ERROR}Błędny wybór. Pozostało prób: {remaining}.{COLOR_RESET}")
    print(f"\n{COLOR_ERROR}Przekroczono limit pomyłek. Zamykanie.{COLOR_RESET}")
    return 'exit'

def run_transform_mode() -> str:
    transformations = {
        1: ("UPPER CASE", "upper"), 2: ("lower case", "lower"), 3: ("Capitalize Case", "capitalize"),
        4: ("Trim White Space", "trim"), 5: ("Convert Polish to Latin", "latinize"),
        6: ("SLUGIFY", "slugify"), 7: ("Text Wrap", "wrap"), 8: ("Format SQL", "format_sql")
    }
    while True:
        print(f"\n{COLOR_INFO}--- Tryb Transformacji Tekstu ---{COLOR_RESET}")
        for key, (name, _) in transformations.items(): print(f"  {key}. {name}")
        choice_str = input(f"\n{COLOR_PROMPT}Wybór (>p, >t, >c, >d, >e): {COLOR_RESET}")
        new_mode = process_global_commands(choice_str)
        if new_mode: return new_mode
        try:
            choice = int(choice_str)
            if choice not in transformations: print(f"{COLOR_ERROR}Błędny numer.{COLOR_RESET}"); continue
            original_text = pyperclip.paste()
            if not isinstance(original_text, str): original_text = ""
            _, type = transformations[choice]
            transformed_text = ""
            if type == 'wrap':
                while True:
                    try:
                        width = int(input(f"  {COLOR_PROMPT}Podaj długość wiersza: {COLOR_RESET}"))
                        if width <= 0: raise ValueError
                        transformed_text = textwrap.fill(original_text, width=width); break
                    except (ValueError, TypeError): print(f"  {COLOR_ERROR}Nieprawidłowa długość.{COLOR_RESET}")
            else:
                if type == 'upper': transformed_text = original_text.upper()
                elif type == 'lower': transformed_text = original_text.lower()
                elif type == 'capitalize': transformed_text = original_text.title()
                elif type == 'trim': transformed_text = re.sub(r'\s+', ' ', original_text.strip())
                elif type == 'latinize': transformed_text = original_text.translate(str.maketrans('ąćęłńóśźżĄĆĘŁŃÓŚŹŻ', 'acelnoszzACELNOSZZ'))
                elif type == 'slugify': transformed_text = slugify(original_text)
                elif type == 'format_sql': transformed_text = format_sql(original_text)
            pyperclip.copy(transformed_text)
            print(f"{COLOR_SUCCESS}Sukces! Wynik operacji '{transformations[choice][0]}' skopiowany.{COLOR_RESET}")
        except ValueError: print(f"{COLOR_ERROR}Nieprawidłowy wybór.{COLOR_RESET}")
        except Exception as e: logging.error(f"Błąd w trybie transformacji: {e}"); print(f"{COLOR_ERROR}Błąd: {e}{COLOR_RESET}")

def run_calculator_mode() -> str:
    safe_dict = {
        "pow": pow, "sqrt": math.sqrt, "fabs": math.fabs, "gcd": math.gcd, "floor": math.floor, "ceil": math.ceil,
        "trunc": math.trunc, "sin": math.sin, "cos": math.cos, "tan": math.tan, "log": math.log, "log10": math.log10,
        "factorial": math.factorial, "pi": math.pi, "e": math.e
    }
    print(f"\n{COLOR_INFO}--- Tryb Kalkulatora ---{COLOR_RESET}")
    print(f"Wpisz wyrażenie. Wpisz {COLOR_PROMPT}>h{COLOR_RESET} po pomoc, lub inną komendę trybu.")
    while True:
        expression = input(f"{COLOR_PROMPT}Kalkulator > {COLOR_RESET}").strip()
        new_mode = process_global_commands(expression)
        if new_mode: return new_mode
        if not expression: continue
        if expression.lower() == '>h':
            print(f"\n{COLOR_INFO}--- Pomoc Kalkulatora ---{COLOR_RESET}")
            print(f"{COLOR_PROMPT}pow(x, y){COLOR_RESET}   - Potęgowanie (x do potęgi y)")
            print(f"{COLOR_PROMPT}sqrt(x){COLOR_RESET}    - Pierwiastek kwadratowy z x")
            print(f"{COLOR_PROMPT}fabs(x){COLOR_RESET}    - Wartość bezwzględna (zwraca float)")
            print(f"{COLOR_PROMPT}gcd(a, b){COLOR_RESET}   - Największy wspólny dzielnik a i b")
            print(f"{COLOR_PROMPT}ceil(x){COLOR_RESET}    - Zaokrąglenie w górę do najbliższej l. całkowitej")
            print(f"{COLOR_PROMPT}floor(x){COLOR_RESET}   - Zaokrąglenie w dół do najbliższej l. całkowitej")
            print(f"{COLOR_PROMPT}trunc(x){COLOR_RESET}   - Obcięcie części ułamkowej (zwraca int)")
            print(f"{COLOR_PROMPT}factorial(x){COLOR_RESET}- Silnia z x (x musi być l. całkowitą nieujemną)")
            print(f"{COLOR_PROMPT}sin(x)|cos(x)|tan(x){COLOR_RESET} - Funkcje trygonometryczne (argument w radianach)")
            print(f"{COLOR_PROMPT}log(x){COLOR_RESET}     - Logarytm naturalny z x")
            print(f"{COLOR_PROMPT}log10(x){COLOR_RESET}   - Logarytm dziesiętny z x")
            print(f"\n{COLOR_INFO}Dostępne stałe:{COLOR_RESET}")
            print(f"{COLOR_PROMPT}pi{COLOR_RESET}, {COLOR_PROMPT}e{COLOR_RESET}")
            print(f"{COLOR_INFO}-------------------------{COLOR_RESET}")
            continue
        try:
            result = eval(expression, {"__builtins__": None}, safe_dict)
            print(f"  {COLOR_SUCCESS}= {result}{COLOR_RESET}")
        except Exception as e: print(f"  {COLOR_ERROR}Błąd w wyrażeniu: {e}{COLOR_RESET}")

def run_date_mode() -> str:
    date_formats = {
        1: ("YYYY-MM-DD HH:MM:SS", "%Y-%m-%d %H:%M:%S"), 2: ("YYYYMMDD_HHMMSS", "%Y%m%d_%H%M%S"),
        3: ("YYYY-MM-DD", "%Y-%m-%d"), 4: ("DD.MM.YYYY", "%d.%m.%Y"), 5: ("HH:MM:SS", "%H:%M:%S"),
        6: ("dd MMMM YYYY (po polsku)", "%d %B %Y"), 7: ("Pełna data (po polsku)", "%A, %d %B %Y, %H:%M:%S"),
        8: ("Timestamp (Unix)", "timestamp")
    }
    while True:
        print(f"\n{COLOR_INFO}--- Tryb Formatera Daty ---{COLOR_RESET}")
        for key, (name, _) in date_formats.items(): print(f"  {key}. {name}")
        choice_str = input(f"\n{COLOR_PROMPT}Wybór (>p, >t, >c, >d, >e): {COLOR_RESET}")
        new_mode = process_global_commands(choice_str)
        if new_mode: return new_mode
        try:
            choice = int(choice_str)
            if choice not in date_formats: print(f"{COLOR_ERROR}Błędny numer.{COLOR_RESET}"); continue
            now = datetime.datetime.now()
            name, code = date_formats[choice]
            formatted_date = str(int(now.timestamp())) if code == "timestamp" else now.strftime(code)
            pyperclip.copy(formatted_date)
            print(f"{COLOR_SUCCESS}Sukces! Data '{formatted_date}' skopiowana.{COLOR_RESET}")
        except ValueError: print(f"{COLOR_ERROR}Nieprawidłowy wybór.{COLOR_RESET}")
        except Exception as e: logging.error(f"Błąd w trybie daty: {e}"); print(f"{COLOR_ERROR}Błąd: {e}{COLOR_RESET}")

def execute_action(action: dict):
    action_type, path, app_path, name = action.get('type'), action.get('path'), action.get('app_path'), action.get('name')
    logging.info(f"Uruchamiam: '{name}'")
    try:
        if action_type == 'program': subprocess.Popen([path])
        elif action_type == 'url': webbrowser.open(path)
        elif action_type in ['file', 'folder']: os.startfile(path)
        elif action_type == 'file_with_app': subprocess.Popen([app_path, path])
    except Exception as e: error_msg = f"Błąd przy uruchamianiu '{name}': {e}"; logging.error(error_msg); print(f"{COLOR_ERROR}BŁĄD: {error_msg}{COLOR_RESET}")

def main():
    """Główna pętla programu - maszyna stanów."""
    os.system(f'title PyPilot - {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    
    config_filename = 'config.json'
    if len(sys.argv) > 1:
        profile_name = sys.argv[1]
        config_filename = f"config_{profile_name}.json"
        print(f"{COLOR_PROMPT}Wczytuję profil: {profile_name}{COLOR_RESET}")
    
    config = load_and_validate_config(config_filename)
    if not config: input("\nNaciśnij Enter..."); sys.exit(1)
    
    config.sort(key=lambda item: item['numer'])
    
    current_mode = 'launcher'
    while True:
        if current_mode == 'launcher':
            current_mode = run_launcher_mode(config)
        elif current_mode == 'transform':
            current_mode = run_transform_mode()
        elif current_mode == 'calculator':
            current_mode = run_calculator_mode()
        elif current_mode == 'date':
            current_mode = run_date_mode()
        elif current_mode == 'exit':
            sys.exit(0)
        else:
            print(f"{COLOR_ERROR}Nieznany błąd trybu. Powrót do menu głównego.{COLOR_RESET}")
            current_mode = 'launcher'

if __name__ == "__main__":
    enable_ansi_colors()
    setup_logging()
    main()