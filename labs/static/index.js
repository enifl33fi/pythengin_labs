import { geocodeWithFallback } from "https://esm.sh/@asksoma/location@1.1.2";

const form = document.getElementById("weather-form");
const cityInput = document.getElementById("city");
const searchButton = document.getElementById("search-button");
const statusElement = document.getElementById("status");
const weatherResult = document.getElementById("weather-result");


// ---------- Автодополнение города ----------

const cityAwesomplete = new Awesomplete(cityInput, {
    minChars: 2,
    autoFirst: true,
    list: [],
    filter: () => true,
    replace: (item) => {
        cityInput.value = item.value;
    },
});

let suggestionTimer = null;

cityInput.addEventListener("input", () => {
    const query = cityInput.value.trim();

    clearTimeout(suggestionTimer);

    if (query.length < 2) {
        cityAwesomplete.list = [];
        return;
    }

    suggestionTimer = setTimeout(async () => {
        try {
            const hits = await geocodeWithFallback(query, 10);

            cityAwesomplete.list = hits.map((hit) => {
                const parts = (hit.display_name || "")
                    .split(",")
                    .map((part) => part.trim())
                    .filter(Boolean);

                const name = parts[0] || hit.name || "";
                const country = parts[parts.length - 1] || "";

                return {
                    label: country ? `${name}, ${country}` : name,
                    value: name,
                };
            });
        } catch {
            // тихо игнорируем сетевые ошибки подсказок
        }
    }, 300);
});


// ---------- Основной поиск прогноза ----------

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const city = cityInput.value.trim();

    if (!city) {
        statusElement.textContent = "Введите название города.";
        return;
    }

    searchButton.disabled = true;
    statusElement.textContent = "Получаем прогноз погоды...";
    weatherResult.hidden = true;

    try {
        const response = await fetch("/api/predict", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ city })
        });

        let data;
        try {
            data = await response.json();
        } catch {
            throw new Error(`Сервер вернул не-JSON (HTTP ${response.status}).`);
        }

        if (!response.ok) {
            throw new Error(data.detail || `HTTP ${response.status}`);
        }

        displayWeather(data);
        statusElement.textContent = "Прогноз успешно получен.";

    } catch (error) {
        statusElement.textContent = `Ошибка: ${error.message}`;
    } finally {
        searchButton.disabled = false;
    }
});


function displayWeather(data) {
    const city = data.city;
    const cityName = typeof city === "string"
        ? city
        : (city?.name || "");
    const country = typeof city === "object" && city
        ? (city.country || "")
        : "";

    const tomorrow = data.tomorrow_weather;
    const prediction = data.prediction;

    document.getElementById("city-name").textContent =
        country ? `${cityName}, ${country}` : cityName;

    document.getElementById("forecast-date").textContent =
        `Прогноз на ${tomorrow.date}`;

    document.getElementById("temperature-max").textContent =
        `${tomorrow.temperature_2m_max} °C`;

    document.getElementById("temperature-min").textContent =
        `${tomorrow.temperature_2m_min} °C`;

    document.getElementById("precipitation").textContent =
        `${tomorrow.precipitation_sum} мм`;

    document.getElementById("wind-speed").textContent =
        `${tomorrow.wind_speed_10m_max} км/ч`;

    updateWeatherScene(prediction);

    weatherResult.hidden = false;
}


function updateWeatherScene(prediction) {
    const scene = document.getElementById("weather-scene");
    if (!scene) return;

    const isRain = prediction.rain_tomorrow === 1;
    const probability = (prediction.rain_probability * 100).toFixed(1);

    scene.classList.remove("is-rain", "is-sun");
    scene.classList.add(isRain ? "is-rain" : "is-sun");

    const title = scene.querySelector(".scene-title");
    const subtitle = scene.querySelector(".scene-subtitle");

    if (title) {
        title.textContent = isRain
            ? "Ожидается дождь"
            : "Дождь не ожидается";
    }

    if (subtitle) {
        subtitle.textContent = isRain
            ? `Вероятность ${probability}% — возьмите зонт и чашку горячего чая.`
            : `Вероятность ${probability}% — хороший день, чтобы выйти на улицу.`;
    }
}


// ---------- Метрики ----------

document.getElementById("metrics-button").addEventListener(
    "click",
    async () => {
        const result = document.getElementById("metrics-result");

        result.textContent = "Загрузка метрик...";

        try {
            const response = await fetch("/api/metrics");
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Ошибка загрузки метрик.");
            }

            result.textContent = JSON.stringify(data, null, 2);

        } catch (error) {
            result.textContent = `Ошибка: ${error.message}`;
        }
    }
);


// ---------- Загрузка / сброс модели ----------

const uploadForm = document.getElementById("upload-form");
const modelFileInput = document.getElementById("model-file");
const uploadButton = document.getElementById("upload-button");
const uploadStatus = document.getElementById("upload-status");

const modelStateBlock = document.getElementById("model-state-block");
const modelStateElement = document.getElementById("model-state");
const resetModelButton = document.getElementById("reset-model-button");


function showUploadedState() {
    modelStateBlock.hidden = false;
    modelStateElement.textContent =
        "Активна загруженная модель. Она живёт только в памяти " +
        "и сбрасывается при перезапуске сервера.";
    resetModelButton.hidden = false;
    resetModelButton.disabled = false;
}


function hideUploadedState() {
    modelStateBlock.hidden = true;
    modelStateElement.textContent = "";
    resetModelButton.hidden = true;
    resetModelButton.disabled = false;
}


async function refreshModelState() {
    try {
        const response = await fetch("/health");
        if (!response.ok) return;

        const data = await response.json();

        if (data.model_source === "uploaded") {
            showUploadedState();
        } else {
            hideUploadedState();
        }
    } catch {
        // сетевые ошибки не критичны — оставляем состояние как есть
    }
}


uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const file = modelFileInput.files[0];

    if (!file) {
        uploadStatus.textContent = "Выберите .pkl-файл.";
        return;
    }

    if (!file.name.toLowerCase().endsWith(".pkl")) {
        uploadStatus.textContent = "Нужен файл с расширением .pkl.";
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    uploadButton.disabled = true;
    uploadStatus.textContent =
        `Загружаем «${file.name}» (${(file.size / 1024 / 1024).toFixed(1)} МБ)...`;

    try {
        const response = await fetch("/upload-model", {
            method: "POST",
            body: formData,
        });

        let data;
        try {
            data = await response.json();
        } catch {
            throw new Error(`Сервер вернул не-JSON (HTTP ${response.status}).`);
        }

        if (!response.ok) {
            throw new Error(data.detail || `HTTP ${response.status}`);
        }

        uploadStatus.textContent =
            data.message || "Модель успешно загружена.";

        modelFileInput.value = "";

        // Кнопка «Очистить» теперь доступна
        showUploadedState();

        // Метрики относились к базовой модели — сбрасываем подсказку
        document.getElementById("metrics-result").textContent =
            "Модель обновлена. Нажмите «Посмотреть метрики», чтобы загрузить актуальные.";

    } catch (error) {
        uploadStatus.textContent = `Ошибка: ${error.message}`;
    } finally {
        uploadButton.disabled = false;
    }
});


resetModelButton.addEventListener("click", async () => {
    resetModelButton.disabled = true;
    uploadStatus.textContent = "Возвращаем базовую модель...";

    try {
        const response = await fetch("/reset-model", { method: "POST" });

        let data;
        try {
            data = await response.json();
        } catch {
            throw new Error(`Сервер вернул не-JSON (HTTP ${response.status}).`);
        }

        if (!response.ok) {
            throw new Error(data.detail || `HTTP ${response.status}`);
        }

        uploadStatus.textContent =
            data.message || "Базовая модель восстановлена.";

        hideUploadedState();

        document.getElementById("metrics-result").textContent = "";

    } catch (error) {
        uploadStatus.textContent = `Ошибка: ${error.message}`;
        resetModelButton.disabled = false;
    }
});

refreshModelState();
