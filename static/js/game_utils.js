/**
 * game_utils.js — сбор поведенческих данных для игр
 * Используется в играх: Раскраска, Диалог, Выбор
 *
 * Подключение: <script src="{% static 'js/game_utils.js' %}"></script>
 *
 * Пример для Раскраски:
 *   GameUtils.initGameSession({ sessionId, userId, gameType: 'Painting' });
 *   // При выборе цвета: GameUtils.painting.trackColorChoice(color, startTime);
 *   await GameUtils.savePainting();
 *
 * Пример для Диалога:
 *   GameUtils.initGameSession({ sessionId, userId, gameType: 'Dialog' });
 *   GameUtils.dialog.startQuestion('question_1');
 *   GameUtils.dialog.trackAnswer('question_1', value, startTime);
 *   await GameUtils.saveDialog();
 *
 * Пример для Выбора:
 *   GameUtils.initGameSession({ sessionId, userId, gameType: 'Choice' });
 *   GameUtils.choice.trackImageView(imgId, roundId);
 *   GameUtils.choice.trackSelection(roundId, value, startTime);
 *   await GameUtils.saveChoice();
 */

const GameUtils = (function() {
    'use strict';

    // Конфигурация сессии
    let config = {
        userId: null,
        sessionId: null,
        gameType: null,
        baseUrl: ''
    };

    // Накопленные данные
    let reactionTimes = [];
    let mistakes = 0;
    let mistakeTypes = {};
    let hintsUsed = 0;
    let actions = [];
    let questionStartTimes = {};
    let imageViewSequence = [];
    let answerChanges = {};

    /**
     * Получить CSRF токен для Django
     */
    function getCsrfToken() {
        const cookie = document.cookie.match(/csrftoken=([^;]+)/);
        if (cookie) return cookie[1];
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    /**
     * Базовый URL API (относительный)
     */
    function getApiUrl(gameType) {
        const base = config.baseUrl || '';
        return `${base}/api/game/${gameType}/${config.userId}/save/`;
    }

    /**
     * 1. Инициализация игровой сессии
     * @param {Object} options - { sessionId, userId, gameType, baseUrl? }
     */
    function initGameSession(options = {}) {
        config = {
            sessionId: options.sessionId || null,
            userId: options.userId || options.user_id || null,
            gameType: options.gameType || options.game_type || null,
            baseUrl: options.baseUrl || ''
        };
        reactionTimes = [];
        mistakes = 0;
        mistakeTypes = {};
        hintsUsed = 0;
        actions = [];
        questionStartTimes = {};
        imageViewSequence = [];
        answerChanges = {};
        return config;
    }

    /**
     * 2. Измерение времени реакции
     * @param {number} startTime - timestamp начала действия (Date.now() или performance.now())
     * @param {Object} action - данные действия { type, data? }
     */
    function trackReactionTime(startTime, action = {}) {
        const elapsed = typeof startTime === 'number' 
            ? (performance.now ? performance.now() - startTime : Date.now() - startTime)
            : 0;
        reactionTimes.push(Math.round(elapsed));
        if (action.type) {
            actions.push({
                type: action.type,
                data: { ...action.data, reactionTime: elapsed },
                timestamp: new Date().toISOString()
            });
        }
        return elapsed;
    }

    /**
     * 3. Учёт ошибок
     * @param {string} type - тип ошибки (attention, inhibition, etc.)
     */
    function trackMistake(type = 'unknown') {
        mistakes += 1;
        mistakeTypes[type] = (mistakeTypes[type] || 0) + 1;
        actions.push({
            type: 'mistake',
            data: { mistakeType: type },
            timestamp: new Date().toISOString()
        });
    }

    /**
     * 4. Учёт использования подсказок
     */
    function trackHint() {
        hintsUsed += 1;
        actions.push({
            type: 'hint_used',
            data: { count: hintsUsed },
            timestamp: new Date().toISOString()
        });
    }

    /**
     * 5. Отправка данных на сервер
     * @param {string} gameType - Painting | Choice | Dialog
     * @param {Object} data - дополнительные данные игры (переопределяют базовые)
     * @returns {Promise<Object>}
     */
    async function saveGameData(gameType, data = {}) {
        const type = gameType || config.gameType;
        if (!type) throw new Error('Не указан тип игры');
        const url = getApiUrl(type);
        const payload = {
            session_id: config.sessionId,
            reaction_times: reactionTimes,
            mistakes,
            actions,
            ...data
        };
        if (Object.keys(mistakeTypes).length) payload.mistake_types = mistakeTypes;
        if (hintsUsed) payload.hints_used = hintsUsed;

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || 'Ошибка сохранения');
        }
        return result;
    }

    /** Сохранение игры «Раскраска» */
    async function savePainting() {
        return saveGameData('Painting', PaintingTracker.getData());
    }

    /** Сохранение игры «Диалог» */
    async function saveDialog() {
        return saveGameData('Dialog', DialogTracker.getData());
    }

    /** Сохранение игры «Выбор» */
    async function saveChoice() {
        return saveGameData('Choice', ChoiceTracker.getData());
    }

    // ==================== ИГРА «РАСКРАСКА» ====================

    const PaintingTracker = {
        colors: [],
        colorChoices: [], // { color, timestamp, reactionTime }

        trackColorChoice(color, startTime) {
            const reactionTime = trackReactionTime(startTime, {
                type: 'color_choice',
                data: { color }
            });
            this.colors.push(color);
            this.colorChoices.push({
                color,
                timestamp: new Date().toISOString(),
                reactionTime
            });
        },

        getData() {
            return {
                colors: this.colors,
                color_choices: this.colorChoices,
                reaction_times: this.colorChoices.map(c => c.reactionTime),
                actions
            };
        }
    };

    // ==================== ИГРА «ДИАЛОГ» ====================

    const DialogTracker = {
        answers: {},
        questionTimes: {},

        startQuestion(questionId) {
            questionStartTimes[questionId] = performance.now ? performance.now() : Date.now();
        },

        trackAnswer(questionId, value, startTime) {
            const t = startTime || questionStartTimes[questionId];
            const reactionTime = t ? trackReactionTime(t, {
                type: 'answer',
                data: { questionId, value }
            }) : 0;
            if (this.answers[questionId] !== undefined) {
                answerChanges[questionId] = (answerChanges[questionId] || 0) + 1;
            }
            this.answers[questionId] = value;
            this.questionTimes[questionId] = reactionTime;
        },

        getData() {
            return {
                answers: this.answers,
                reaction_times: Object.values(this.questionTimes),
                answer_changes: answerChanges
            };
        }
    };

    // ==================== ИГРА «ВЫБОР» ====================

    const ChoiceTracker = {
        choices: {},
        selectionTimes: {},
        viewSequence: [],

        trackImageView(imageId, roundId) {
            this.viewSequence.push({
                imageId,
                roundId,
                timestamp: new Date().toISOString()
            });
        },

        trackSelection(roundId, value, startTime) {
            const reactionTime = trackReactionTime(startTime, {
                type: 'image_selection',
                data: { roundId, value }
            });
            this.choices[`round_${roundId}`] = value;
            this.selectionTimes[roundId] = reactionTime;
        },

        getData() {
            return {
                choices: this.choices,
                reaction_times: Object.values(this.selectionTimes),
                view_sequence: this.viewSequence
            };
        }
    };

    // Публичный API
    return {
        initGameSession,
        trackReactionTime,
        trackMistake,
        trackHint,
        saveGameData,
        savePainting,
        saveDialog,
        saveChoice,

        // Игры
        painting: PaintingTracker,
        dialog: DialogTracker,
        choice: ChoiceTracker,

        // Вспомогательные
        getConfig: () => ({ ...config }),
        getReactionTimes: () => [...reactionTimes],
        getMistakes: () => mistakes,
        getActions: () => [...actions]
    };
})();

// Экспорт для модулей
if (typeof module !== 'undefined' && module.exports) {
    module.exports = GameUtils;
}
