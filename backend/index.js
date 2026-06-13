require('dotenv').config();
const express = require('express');
const cors = require('cors');
const { createClient } = require('@supabase/supabase-js');

const app = express();
app.use(cors()); // Разрешаем лаунчеру подключаться к серверу
app.use(express.json());

// Подключаем Supabase с правами суперадмина
const supabase = createClient(process.env.URL, process.env.SERVICE_ROLE_KEY);

// Функция для получения реального курса валют (рубль к доллару и тенге)
async function getCurrencyRates() {
    try {
        // Используем бесплатное и стабильное API ЦБ РФ
        const response = await fetch('https://cbr-xml-daily.ru');
        const data = await response.json();
        
        return {
            USD: 1 / data.Valute.USD.Value, // сколько баксов в одном рубле
            KZT: 100 / data.Valute.KZT.Value // сколько тенге в одном рубле
        };
    } catch (error) {
        console.log('Ошибка получения курса валют, ставим базовый:', error);
        // Запасной курс на случай, если API лежит
        return { USD: 0.011, KZT: 5.2 }; 
    }
}

// 1. ПОЛУЧИТЬ ВСЕ ИГРЫ (с авто-пересчетом цены по реальному курсу)
app.get('/api/games', async (req, res) => {
    const userCurrency = req.query.currency || 'RUB';
    
    // Берем игры из базы Supabase
    const { data: games, error } = await supabase.from('games').select('*');
    if (error) return res.status(500).json({ error: error.message });

    const rates = await getCurrencyRates();

    // Пересчитываем цену для каждой игры на лету
    const convertedGames = games.map(game => {
        let finalPrice = Number(game.price_rub);
        let sign = '₽';

        if (userCurrency === 'USD') {
            finalPrice = finalPrice * rates.USD;
            sign = '$';
        } else if (userCurrency === 'KZT') {
            finalPrice = finalPrice * rates.KZT;
            sign = '₸';
        }

        return {
            ...game,
            display_price: `${finalPrice.toFixed(2)} ${sign}`
        };
    });

    res.json(convertedGames);
});

// 2. АКТИВАЦИЯ ПРОМОКОДА
app.post('/api/promo/activate', async (req, res) => {
    const { code, userId, currency } = req.body;

    // Ищем промокод в таблице Supabase
    const { data: promo, error } = await supabase.from('promo_codes').select('*').eq('code', code.toUpperCase()).single();
    if (error || !promo) return res.status(404).json({ error: "Промокод не найден!" });

    // Проверяем, не использовал ли его этот юзер ранее
    if (promo.is_used_by && promo.is_used_by.includes(userId)) {
        return res.status(400).json({ error: "Вы уже активировали этот промокод!" });
    }

    // Считаем сумму бонуса по курсу валюты юзера
    const rates = await getCurrencyRates();
    let rate = 1;
    let sign = '₽';

    if (currency === 'USD') { rate = rates.USD; sign = '$'; }
    if (currency === 'KZT') { rate = rates.KZT; sign = '₸'; }
    
    const reward = promo.reward_rub * rate;

    // Получаем текущий баланс юзера и прибавляем бонус
    const { data: profile } = await supabase.from('profiles').select('balance').eq('id', userId).single();
    const newBalance = Number(profile.balance) + reward;

    // Обновляем баланс в базе profiles
    await supabase.from('profiles').update({ balance: newBalance }).eq('id', userId);

    // Добавляем ID юзера в список использовавших этот код
    const updatedUsers = [...(promo.is_used_by || []), userId];
    await supabase.from('promo_codes').update({ is_used_by: updatedUsers }).eq('id', promo.id);

    res.json({ success: true, reward: reward.toFixed(2), sign });
});

// 3. ДОБАВЛЕНИЕ ИГРЫ (Маршрут из админки)
app.post('/api/admin/add-game', async (req, res) => {
    const { password, title, price_rub, download_url, exe_path, cover_url } = req.body;
    
    // Проверяем пароль админа из файла .env
    if (password !== process.env.ADMIN_PASSWORD) {
        return res.status(403).json({ error: "Неверный пароль администратора!" });
    }

    // Делаем INSERT запрос в Supabase
    const { data, error } = await supabase.from('games').insert([{ title, price_rub, download_url, exe_path, cover_url }]);
    if (error) return res.status(500).json({ error: error.message });

    res.json({ success: true, message: "Игра успешно опубликована в RedDemo!" });
});

const PORT = 3000;
app.listen(PORT, () => console.log(`🚀 Сервер RedDemo API успешно запущен на порту ${PORT}`));
