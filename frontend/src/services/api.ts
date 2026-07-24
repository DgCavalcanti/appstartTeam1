import axios from 'axios';

/**
 * Cliente HTTP do SAA.
 *
 * O sistema é de uso local por um único gestor — sem autenticação,
 * portanto sem interceptors de token.
 */
// Sem Content-Type fixo de propósito: o axios já usa application/json para
// objetos comuns e deixa o navegador montar o multipart/form-data (com o
// boundary) quando o corpo é um FormData. Fixar o header aqui apagaria o
// boundary e o upload da planilha chegaria ilegível ao backend.
const api = axios.create({
  baseURL: '/',
});

export default api;
