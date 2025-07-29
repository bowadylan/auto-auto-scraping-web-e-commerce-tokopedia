import time
import os
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


class ReviewScraper:
    def __init__(self, url: str):
        self.url = url
        self.data = []

        options = Options()
        # options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        self.driver = webdriver.Chrome(options=options)

    def clean_text(self, text: str) -> str:
        return text.replace('\n', ' ').strip()

    def get_review_data(self, container) -> dict:
        try:
            username_el = container.find('span', class_='name')
            review_el = container.find('span', attrs={'data-testid': 'lblItemUlasan'})
            rating_el = container.find('div', attrs={'data-testid': 'icnStarRating'})

            username = self.clean_text(username_el.text) if username_el else "N/A"
            ulasan = self.clean_text(review_el.text) if review_el else ""
            rating = rating_el.get('aria-label').split(' ')[1] if rating_el and rating_el.has_attr('aria-label') else "0"

            if not ulasan:
                return None

            return {
                'Username': username,
                'Review': ulasan,
                'Rating': rating
            }
        except Exception as e:
            print("Gagal parsing 1 review:", e)
            return None

    def scroll_to_reviews(self, max_retries=5):
        retry = 0
        while retry < max_retries:
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.6);")
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "review-feed"))
                )
                return True
            except Exception:
                retry += 1
                print(f"Scroll gagal (percobaan {retry}/{max_retries})... coba lagi.")
                time.sleep(2)
        return False

    def click_next_page(self, max_retries=3):
        for attempt in range(max_retries):
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                next_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label^='Laman berikutnya']"))
                )
                self.driver.execute_script("arguments[0].click();", next_btn)
                print(f"➡️ Next (percobaan {attempt+1})")
                return True
            except Exception as e:
                print(f"🔁 Gagal klik next (percobaan {attempt+1}): {e}")
                time.sleep(2)
        print("✅ Tidak ada tombol Laman berikutnya.")
        return False

    def load_all_reviews(self) -> list[dict]:
        page_number = 1
        last_count = 0

        while True:
            if not self.scroll_to_reviews():
                break

            time.sleep(2)
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            review_section = soup.find("section", attrs={'id': 'review-feed'})

            if not review_section:
                print("❌ Review section tidak ditemukan.")
                break

            containers = review_section.find_all("article")
            if not containers:
                print("❌ Tidak ada review ditemukan.")
                break

            for container in containers:
                review_data = self.get_review_data(container)
                if review_data:
                    self.data.append(review_data)

            print(f"✅ Page {page_number}: {len(containers)} review diambil. Total: {len(self.data)}")

            # 💡 Batas deteksi akhir jika jumlah review sangat sedikit
            if len(containers) < 10:
                print("🛑 Review sedikit. Kemungkinan sudah sampai halaman terakhir.")
                break

            if len(self.data) == last_count:
                print("🛑 Review tidak bertambah. Kemungkinan sudah sampai halaman terakhir.")
                break
            last_count = len(self.data)

            if not self.click_next_page():
                break

            time.sleep(3)
            page_number += 1

        return self.data

    def run(self) -> pd.DataFrame:
        self.driver.get(self.url)
        self.driver.minimize_window()
        time.sleep(3)

        review_data = self.load_all_reviews()
        self.driver.quit()

        return pd.DataFrame(review_data) if review_data else pd.DataFrame()


def main():
    try:
        banyak = int(input("🔢 Mau scrape berapa produk? "))
        if banyak <= 0:
            raise ValueError("Jumlah harus lebih dari 0")
    except ValueError:
        print("❌ Input tidak valid.")
        return

    links = []
    for i in range(banyak):
        url = input(f"🔗 Masukkan URL produk ke-{i+1}: ").strip()
        if not url.startswith("http"):
            print("❌ URL tidak valid. Lewatkan.")
            continue
        links.append(url)

    print(f"\n🚀 Mulai proses scraping {len(links)} produk...\n")

    semua_data = pd.DataFrame()

    for i, url in enumerate(links):
        print(f"🔍 Scraping produk {i+1} dari {len(links)}")
        scraper = ReviewScraper(url)
        df = scraper.run()
        if not df.empty:
            semua_data = pd.concat([semua_data, df], ignore_index=True)
        else:
            print("⚠️ Tidak ada review dari link ini.")

    if semua_data.empty:
        print("\n❌ Tidak ada data yang bisa disimpan.")
        return

    semua_data.drop_duplicates(subset=["Username", "Review"], inplace=True)
    file_path = "tokopedia_reviews.csv"
    if os.path.exists(file_path):
        df_existing = pd.read_csv(file_path)
        combined_df = pd.concat([df_existing, semua_data], ignore_index=True)
        combined_df.drop_duplicates(subset=["Username", "Review"], inplace=True)
        combined_df.to_csv(file_path, index=False)
        print(f"\n✅ Review baru ditambahkan. Total review sekarang: {len(combined_df)}")
    else:
        semua_data.to_csv(file_path, index=False)
        print(f"\n🎉 File baru 'tokopedia_reviews.csv' dibuat dengan {len(semua_data)} review.")

    input("\nTekan ENTER untuk keluar...")


if __name__ == "__main__":
    main()
