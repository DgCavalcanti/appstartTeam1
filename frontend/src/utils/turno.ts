/**
 * Rótulos de dia e turno, num único lugar — antes o mapa vivia duplicado em
 * cada tela (Importação, Cenário, Visualização).
 */
export interface Turno {
  dia: string;
  periodo: string;
}

const DIA_COMPLETO: Record<string, string> = {
  segunda: 'Segunda',
  terca: 'Terça',
  quarta: 'Quarta',
  quinta: 'Quinta',
  sexta: 'Sexta',
};

/** Nome do dia por extenso ("Segunda"), com fallback para o valor cru. */
export function rotuloDia(dia: string): string {
  return DIA_COMPLETO[dia] ?? dia;
}

/** Turno por extenso ("Manhã" / "Tarde"). */
export function rotuloPeriodo(periodo: string): string {
  return periodo === 'manha' ? 'Manhã' : 'Tarde';
}

/**
 * Rótulo do turno em duas linhas: dia em cima, período embaixo. O `\n` é o que
 * permite empilhar — quem exibe decide como quebrar (o PlanilhaEditavel divide
 * por `\n`; as tabelas próprias usam <span> separados).
 */
export function rotuloTurno(t: Turno): string {
  return `${rotuloDia(t.dia)}\n${rotuloPeriodo(t.periodo)}`;
}
