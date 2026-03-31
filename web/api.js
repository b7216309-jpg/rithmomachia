/**
 * Fetch wrapper for Rithmomachia backend API calls.
 * All game logic lives on the server — this is just the transport layer.
 */

const API_BASE = '/api/game';

async function apiCall(path, options = {}) {
    const resp = await fetch(`${API_BASE}${path}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    if (!resp.ok && resp.status !== 200) {
        const text = await resp.text();
        throw new Error(`API ${resp.status}: ${text}`);
    }
    return resp.json();
}

const Api = {
    newGame(white = 'human', black = 'human', whiteName = 'White', blackName = 'Black', whiteDesc = '', blackDesc = '') {
        return apiCall('/new', {
            method: 'POST',
            body: JSON.stringify({
                white, black,
                white_name: whiteName, black_name: blackName,
                white_description: whiteDesc, black_description: blackDesc,
            }),
        });
    },

    join(gameId, color, name = 'Player', description = '') {
        return apiCall(`/${gameId}/join`, {
            method: 'POST',
            body: JSON.stringify({ color, name, description }),
        });
    },

    getState(gameId) {
        return apiCall(`/${gameId}/state`);
    },

    getLegal(gameId) {
        return apiCall(`/${gameId}/legal`);
    },

    submitMove(gameId, aiid, notation) {
        return apiCall(`/${gameId}/move`, {
            method: 'POST',
            body: JSON.stringify({ aiid, notation }),
        });
    },

    getHistory(gameId) {
        return apiCall(`/${gameId}/history`);
    },

    resign(gameId, aiid) {
        return apiCall(`/${gameId}/resign`, {
            method: 'POST',
            body: JSON.stringify({ aiid }),
        });
    },

    waitForMove(gameId, afterTurn) {
        return apiCall(`/${gameId}/wait?after_turn=${afterTurn}`);
    },

    registerSpectator(gameId) {
        return apiCall(`/${gameId}/spectate`, { method: 'POST' });
    },

    getGameHistory(limit = 50) {
        return apiCall(`/history/all?limit=${limit}`);
    },

    joinAsCommentator(gameId, name = 'Commentator', description = '') {
        return apiCall(`/${gameId}/commentate`, {
            method: 'POST',
            body: JSON.stringify({ name, description }),
        });
    },

    postComment(gameId, aiid, message) {
        return apiCall(`/${gameId}/comment`, {
            method: 'POST',
            body: JSON.stringify({ aiid, message }),
        });
    },

    getComments(gameId, after = 0) {
        return apiCall(`/${gameId}/comments?after=${after}`);
    },

    waitForComment(gameId, after = 0) {
        return apiCall(`/${gameId}/comments/wait?after=${after}`);
    },

    vote(gameId, color) {
        return apiCall(`/${gameId}/vote?color=${color}`, { method: 'POST' });
    },

    getVotes(gameId) {
        return apiCall(`/${gameId}/votes`);
    },
};
