import { describe, it, expect, beforeEach, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';

import SaaVisualizacao from '../SaaVisualizacao.vue';
import api from '../../services/api';

vi.mock('../../services/api', () => ({ default: { get: vi.fn() } }));
vi.mock('vue-router', () => ({ useRoute: () => ({ params: { id: '1' } }) }));

const turnos = [
  { dia: 'segunda', periodo: 'manha' }, { dia: 'segunda', periodo: 'tarde' },
  { dia: 'terca', periodo: 'manha' }, { dia: 'terca', periodo: 'tarde' },
  { dia: 'quarta', periodo: 'manha' }, { dia: 'quarta', periodo: 'tarde' },
  { dia: 'quinta', periodo: 'manha' }, { dia: 'quinta', periodo: 'tarde' },
  { dia: 'sexta', periodo: 'manha' }, { dia: 'sexta', periodo: 'tarde' },
];

const vetor = (q: number) => Array.from({ length: 10 }, () => q);

const PAINEL = {
  id: 1, nome: 'Cenário 1', status: 'em_andamento', desatualizada: false,
  turnos,
  resumo: {
    total_alocado: 40, total_nao_alocado: 0, total_demanda: 40,
    clinicas_alocadas: 3, clinicas_com_sobra: 0,
    pavimentos_usados: 2, pavimentos_totais: 2,
    salas_no_pico: 20, salas_totais: 30, ocupacao_media_pct: 66.7,
  },
  por_pavimento: [
    {
      id: 1, nome: 'Bloco E — 2º Pavimento', capacidade: 20, salas_abertas: 15,
      ocupacao: vetor(4), nao_alocado: vetor(0), total_nao_alocado: 0,
      salas_por_turno: vetor(4), salas_no_pico: 12,
      ocupacao_media_pct: 20, ocupacao_pico_pct: 20, clinicas: ['OFTALMOLOGIA (AMBULATÓRIO)'],
      alertas: [],
    },
    {
      id: 2, nome: 'Bloco F — 5º Pavimento', capacidade: 22, salas_abertas: 22,
      ocupacao: vetor(2), nao_alocado: vetor(0), total_nao_alocado: 0,
      salas_por_turno: vetor(2), salas_no_pico: 2,
      ocupacao_media_pct: 9, ocupacao_pico_pct: 9, clinicas: ['CARDIOLOGIA (AMBULATÓRIO)'],
      alertas: [],
    },
  ],
  por_turno: turnos.map((t, i) => ({
    ...t, alocado: i === 0 ? 10 : 4, nao_alocado: i === 0 ? 2 : 0,
    demanda: i === 0 ? 12 : 4, ocupacao_pct: i === 0 ? 80 : 30,
  })),
  // Bloco e pavimento (andar) separados. PEDIATRIA fica no 2º Pavimento do
  // Bloco F, então "2º Pavimento" cruza dois blocos (Bloco E e Bloco F).
  por_clinica: [
    { nome: 'OFTALMOLOGIA (AMBULATÓRIO)', bloco: 'Bloco E', pavimento: '2º Pavimento', alocado: vetor(2), nao_alocado: vetor(0), total_alocado: 20, total_nao_alocado: 0 },
    { nome: 'ORTOPEDIA (AMBULATÓRIO)', bloco: 'Bloco E', pavimento: '3º Pavimento', alocado: vetor(1), nao_alocado: vetor(0), total_alocado: 10, total_nao_alocado: 0 },
    { nome: 'CARDIOLOGIA (AMBULATÓRIO)', bloco: 'Bloco F', pavimento: '5º Pavimento', alocado: vetor(1), nao_alocado: vetor(0), total_alocado: 10, total_nao_alocado: 0 },
    { nome: 'PEDIATRIA (AMBULATÓRIO)', bloco: 'Bloco F', pavimento: '2º Pavimento', alocado: vetor(1), nao_alocado: vetor(0), total_alocado: 10, total_nao_alocado: 0 },
  ],
};

async function montar() {
  (api.get as any).mockResolvedValue({ data: PAINEL });
  const wrapper = mount(SaaVisualizacao);
  await flushPromises();
  return wrapper;
}

/** As linhas de clínica da tabela de distribuição (exclui o aviso de vazio). */
function nomesVisiveis(wrapper: any): string[] {
  return wrapper
    .findAll('tbody tr')
    .map((tr: any) => tr.find('td').text().trim())
    .filter((n: string) => n && !n.includes('Nenhuma'));
}

describe('SaaVisualizacao.vue', () => {
  beforeEach(() => vi.clearAllMocks());

  it('carrega e mostra os indicadores gerais', async () => {
    const wrapper = await montar();
    expect(wrapper.text()).toContain('Painel consolidado');
    expect(wrapper.text()).toContain('20');   // salas no pico
    expect(wrapper.text()).toContain('66.7%'); // ocupação média
  });

  // ── Gráfico de ocupação por turno ──────────────────────────────────────

  it('desenha as barras do gráfico com altura em pixels', async () => {
    const wrapper = await montar();

    const barras = wrapper
      .findAll('div[style*="height"]')
      .map(d => (d.element as HTMLElement).style.height)
      .filter(h => h.endsWith('px') && h !== '128px'); // exclui a área-contêiner

    expect(barras.length).toBeGreaterThan(0);
    // Nenhuma barra pode colapsar para 0px quando há demanda — era o bug.
    expect(barras.some(h => parseInt(h) > 0)).toBe(true);
    // A barra do turno de pico (demanda 12) deve ser a mais alta.
    const alturas = barras.map(h => parseInt(h));
    expect(Math.max(...alturas)).toBeGreaterThanOrEqual(100);
  });

  // ── Filtro da distribuição das clínicas ────────────────────────────────

  // As colunas Pavimento e Bloco são as posições 1 e 2 dos dois <select>.
  const selectBloco = (w: any) => w.findAll('select')[0];
  const selectPavimento = (w: any) => w.findAll('select')[1];

  it('mostra todas as clínicas sem filtro', async () => {
    const wrapper = await montar();
    expect(nomesVisiveis(wrapper)).toHaveLength(4);
    expect(wrapper.text()).toContain('Mostrando 4 de 4');
  });

  it('separa pavimento e bloco em colunas distintas', async () => {
    const wrapper = await montar();
    const cabecalhos = wrapper.findAll('thead th').map(th => th.text());
    expect(cabecalhos).toContain('Pavimento');
    expect(cabecalhos).toContain('Bloco');

    // A lista vem em ordem alfabética (visão secundária) — busca a linha da
    // OFTALMOLOGIA pelo nome em vez de assumir a posição.
    const linha = wrapper
      .findAll('tbody tr')
      .find(tr => tr.text().includes('OFTALMOLOGIA'))!;
    const celulas = linha.findAll('td');
    expect(celulas[1].text()).toBe('2º Pavimento'); // coluna Pavimento (andar)
    expect(celulas[2].text()).toBe('Bloco E');       // coluna Bloco
  });

  it('busca por nome de clínica (oftalmologia)', async () => {
    const wrapper = await montar();
    await wrapper.find('input[type=search]').setValue('oftalmologia');
    expect(nomesVisiveis(wrapper)).toEqual(['OFTALMOLOGIA (AMBULATÓRIO)']);
  });

  it('busca ignora acento e caixa', async () => {
    const wrapper = await montar();
    await wrapper.find('input[type=search]').setValue('CARDIOLOGÍA');
    expect(nomesVisiveis(wrapper)).toEqual(['CARDIOLOGIA (AMBULATÓRIO)']);
  });

  it('filtra por bloco (todas as clínicas do Bloco E)', async () => {
    const wrapper = await montar();
    await selectBloco(wrapper).setValue('Bloco E');

    expect(nomesVisiveis(wrapper).sort()).toEqual([
      'OFTALMOLOGIA (AMBULATÓRIO)', 'ORTOPEDIA (AMBULATÓRIO)',
    ]);
  });

  it('filtra por pavimento cruzando blocos (2º Pavimento)', async () => {
    const wrapper = await montar();
    await selectPavimento(wrapper).setValue('2º Pavimento');

    // O 2º Pavimento existe no Bloco E e no Bloco F — ambos aparecem.
    expect(nomesVisiveis(wrapper).sort()).toEqual([
      'OFTALMOLOGIA (AMBULATÓRIO)', 'PEDIATRIA (AMBULATÓRIO)',
    ]);
  });

  it('combina bloco e pavimento (Bloco E, 2º Pavimento)', async () => {
    const wrapper = await montar();
    await selectBloco(wrapper).setValue('Bloco E');
    await selectPavimento(wrapper).setValue('2º Pavimento');

    expect(nomesVisiveis(wrapper)).toEqual(['OFTALMOLOGIA (AMBULATÓRIO)']);
    expect(wrapper.text()).toContain('Mostrando 1 de 4');
  });

  it('os seletores listam só blocos e pavimentos com clínicas', async () => {
    const wrapper = await montar();
    const blocos = selectBloco(wrapper).findAll('option').map((o: any) => o.text());
    const pavimentos = selectPavimento(wrapper).findAll('option').map((o: any) => o.text());

    expect(blocos).toEqual(['Todos os blocos', 'Bloco E', 'Bloco F']);
    expect(pavimentos).toContain('2º Pavimento');
    expect(pavimentos).toContain('5º Pavimento');
  });

  it('avisa quando nada corresponde ao filtro', async () => {
    const wrapper = await montar();
    await wrapper.find('input[type=search]').setValue('inexistente xyz');

    expect(nomesVisiveis(wrapper)).toHaveLength(0);
    expect(wrapper.text()).toContain('Nenhuma clínica corresponde');
  });

  it('avisa quando o cenário não foi alocado (409)', async () => {
    (api.get as any).mockRejectedValue({ response: { status: 409 } });
    const wrapper = mount(SaaVisualizacao);
    await flushPromises();

    expect(wrapper.text()).toContain('ainda não foi alocado');
  });
});
