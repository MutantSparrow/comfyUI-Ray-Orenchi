export const api = {
    apiURL(url) {
        const second = url.includes('second');
        return 'data:image/svg+xml,' + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="${second ? 400 : 600}" height="400"><rect width="100%" height="100%" fill="${second ? '#364d67' : '#a9764b'}"/><circle cx="200" cy="180" r="100" fill="${second ? '#8eb5ba' : '#ead1a3'}"/><text x="200" y="330" text-anchor="middle" fill="white" font-family="sans-serif" font-size="30">Image ${second ? 2 : 1}</text></svg>`);
    },
    async fetchApi() {
        return {ok:true, async json() {return {path:'C:/Images',parent:'C:/',roots:['C:/'],folders:[{name:'Exports',path:'C:/Images/Exports'}]};}};
    },
};
