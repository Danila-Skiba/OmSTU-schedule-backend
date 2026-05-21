import requests
import time
import statistics
import csv
import matplotlib.pyplot as plt
import os

GATEWAY_URL = "http://localhost:8000"
ITERATIONS  = 100

SUBJECTS = [
    "Математический анализ",
    "Линейная алгебра",
    "Численные методы",
    "Теория вероятностей",
    "Физика",
    "Базы данных",
    "Алгоритмы",
    "Операционные системы",
]


def get_token() -> str:
    """Получаем токен для тестов."""
    response = requests.post(
        f"{GATEWAY_URL}/api/auth/login",
        json={"email": "test@gmail.com", "password": "1234"}
    )
    return response.json()["access_token"]


def run_benchmark(token: str) -> list[float]:
    timings = []
    headers = {"Authorization": f"Bearer {token}"}

    print(f"Запускаем {ITERATIONS} запросов...\n")

    for i in range(ITERATIONS):
        import random
        subject = random.choice(SUBJECTS)

        url = f"{GATEWAY_URL}/api/lectures/session"
        params = {"subject": subject}

        start = time.time()
        try:
            response = requests.post(url, headers=headers, params=params, timeout=30)
            elapsed = time.time() - start
            status  = response.status_code
        except Exception as e:
            elapsed = time.time() - start
            status  = 0
            print(f"  Ошибка: {e}")

        timings.append(elapsed)
        print(f"[{i+1:>3}/100] subject={subject[:20]:<20} | {elapsed:.3f}s | {status}")

    return timings


def calc_stats(timings: list[float]):
    mean     = statistics.mean(timings)
    variance = statistics.variance(timings)
    std      = statistics.stdev(timings)

    print(f"\n{'='*40}")
    print(f"Среднее:   {mean:.4f} сек")
    print(f"Дисперсия: {variance:.6f}")
    print(f"Std:       {std:.4f} сек")
    print(f"Минимум:   {min(timings):.4f} сек")
    print(f"Максимум:  {max(timings):.4f} сек")
    print(f"{'='*40}")

    return mean, variance, std


def save_results(timings: list[float], mean: float, variance: float, std: float):
    os.makedirs("results/msgpack", exist_ok=True)

    # CSV
    with open("results/msgpack/timings.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["iteration", "time_seconds"])
        for i, t in enumerate(timings, 1):
            writer.writerow([i, round(t, 6)])

    # Статистика
    with open("results/msgpack/stats.txt", "w") as f:
        f.write(f"Протокол:  REST + JSON\n")
        f.write(f"Запрос:    POST /api/lectures/session\n")
        f.write(f"Цепочка:   Gateway → auth-service → lecture-service → PostgreSQL\n")
        f.write(f"Итераций:  {len(timings)}\n\n")
        f.write(f"Среднее:   {mean:.4f} сек\n")
        f.write(f"Дисперсия: {variance:.6f}\n")
        f.write(f"Std:       {std:.4f} сек\n")
        f.write(f"Минимум:   {min(timings):.4f} сек\n")
        f.write(f"Максимум:  {max(timings):.4f} сек\n")

    # График
    plt.figure(figsize=(12, 5))
    plt.plot(range(1, len(timings) + 1), timings, linewidth=0.8, color="#6c5ce7", alpha=0.8)
    plt.axhline(y=mean, color="#e17055", linestyle="--", linewidth=1.5, label=f"Среднее: {mean:.3f}s")
    plt.fill_between(range(1, len(timings) + 1), timings, alpha=0.1, color="#6c5ce7")
    plt.xlabel("Номер вызова")
    plt.ylabel("Время (сек)")
    plt.title("REST — POST /api/lectures/session\nGateway → auth-service → lecture-service → PostgreSQL")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("results/msgpack/plot.png", dpi=150)
    plt.close()

    print("\nРезультаты сохранены в results/msgpack/")


if __name__ == "__main__":
    print("Получаем токен...")
    token = get_token()
    print(f"Токен получен ✓\n")

    timings        = run_benchmark(token)
    mean, var, std = calc_stats(timings)
    save_results(timings, mean, var, std)