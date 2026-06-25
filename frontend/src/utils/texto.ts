/**
 * Utilitarios de normalizacao de texto para busca.
 *
 * `normalizarBusca` remove acentos/diacriticos e diferencas de
 * maiusculas/minusculas, para que buscas como "cardiologia", "CARDIOLOGIA"
 * ou "Cardiologia" (com ou sem acento) encontrem o mesmo resultado.
 */
export function normalizarBusca(texto: string | null | undefined): string {
  if (!texto) return '';
  return texto
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim();
}

/** Verifica se `valor` contem `busca`, ignorando acentos e caixa. */
export function contemSemAcento(valor: string | null | undefined, busca: string | null | undefined): boolean {
  if (!busca) return true;
  return normalizarBusca(valor).includes(normalizarBusca(busca));
}
