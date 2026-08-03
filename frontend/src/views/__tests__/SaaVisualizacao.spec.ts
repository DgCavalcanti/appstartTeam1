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
    total_alocado: 40, total_nao_alocado: 1, total_demanda: 41,
    clinicas_alocadas: 3, clinicas_com_sobra: 1,
    pavimentos_usados: 3, pavimentos_totais: 3,
    salas_no_pico: 20, salas_totais: 30, ocupacao_media_pct: 66.7,
  },
  // Dois blocos no 2º Pavimento (andar 2) + um no 5º — testa o agrupamento por
  // andar. `clinicas` agora traz a linha de 10 turnos de cada clínica.
  por_pavimento: [
    {
      id: 1, andar: 2, bloco: 'Bloco E', pavimento: '2º Pavimento', nome: 'Bloco E — 2º Pavimento',
      capacidade: 20, salas_abertas: 15,
      ocupacao: vetor(4), nao_alocado: [1, 0, 0, 0, 0, 0, 0, 0, 0, 0], total_nao_alocado: 1,
      salas_por_turno: vetor(4), salas_no_pico: 12,
      ocupacao_media_pct: 20, ocupacao_pico_pct: 20,
      clinicas: [
        { nome: 'OFTALMOLOGIA (AMBULATÓRIO)', alocado: vetor(2), nao_alocado: [1, 0, 0, 0, 0, 0, 0, 0, 0, 0], total_alocado: 20, total_nao_alocado: 1 },
      ],
      alertas: [{ tipo: 'excesso', mensagem: 'Capacidade excedida: 1 grade(s) sem sala neste pavimento.' }],
    },
    {
      id: 2, andar: 2, bloco: 'Bloco F', pavimento: '2º Pavimento', nome: 'Bloco F — 2º Pavimento',
      capacidade: 22, salas_abertas: 22,
      ocupacao: vetor(2), nao_alocado: vetor(0), total_nao_alocado: 0,
      salas_por_turno: vetor(2), salas_no_pico: 2,
      ocupacao_media_pct: 9, ocupacao_pico_pct: 9,
      clinicas: [
        { nome: 'CARDIOLOGIA (AMBULATÓRIO)', alocado: vetor(1), nao_alocado: vetor(0), total_alocado: 10, total_nao_alocado: 0 },
      ],
      alertas: [],
    },
    {
      id: 3, andar: 5, bloco: 'Bloco F', pavimento: '5º Pavimento', nome: 'Bloco F — 5º Pavimento',
      capacidade: 22, salas_abertas: 22,
      ocupacao: vetor(1), nao_alocado: vetor(0), total_nao_alocado: 0,
      salas_por_turno: vetor(1), salas_no_pico: 1,
      ocupacao_media_pct: 5, ocupacao_pico_pct: 5,
      clinicas: [
        { nome: 'PEDIATRIA (AMBULATÓRIO)', alocado: vetor(1), nao_alocado: vetor(0), total_alocado: 10, total_nao_alocado: 0 },
      ],
      alertas: [],
    },
  ],
  por_turno: turnos.map((t, i) => ({
    ...t, alocado: i === 0 ? 10 : 4, nao_alocado: i === 0 ? 2 : 0,
    demanda: i === 0 ? 12 : 4, ocupacao_pct: i === 0 ? 80 : 30,
  })),
};

async function montar() {
  (api.get as any).mockResolvedValue({ data: PAINEL });
  const wrapper = mount(SaaVisualizacao);
  await flushPromises();
  return wrapper;
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

  // ── Nova visão: acordeão pavimento → bloco → clínica ───────────────────

  async function abrirAndar(wrapper: any, rotulo: string) {
    const botao = wrapper.findAll('button').find((b: any) => b.text().includes(rotulo));
    await botao!.trigger('click');
  }

  it('lista os andares e começa colapsado', async () => {
    const wrapper = await montar();
    const texto = wrapper.text();
    expect(texto).toContain('2º Pavimento');
    expect(texto).toContain('5º Pavimento');
    // Fechado por padrão: as clínicas só aparecem depois de abrir o andar.
    expect(texto).not.toContain('OFTALMOLOGIA');
  });

  it('sinaliza no cabeçalho do andar quando há grade sem sala', async () => {
    const wrapper = await montar();
    // O 2º Pavimento tem 1 grade sem sala — visível já com o andar fechado.
    expect(wrapper.text()).toContain('1 sem sala');
  });

  it('abre um andar e mostra seus blocos e clínicas', async () => {
    const wrapper = await montar();
    await abrirAndar(wrapper, '2º Pavimento');
    const texto = wrapper.text();
    expect(texto).toContain('Bloco E');
    expect(texto).toContain('Bloco F');
    expect(texto).toContain('OFTALMOLOGIA (AMBULATÓRIO)');
    expect(texto).toContain('CARDIOLOGIA (AMBULATÓRIO)');
  });

  it('desenha uma faixa de 10 turnos para cada clínica do andar aberto', async () => {
    const wrapper = await montar();
    await abrirAndar(wrapper, '2º Pavimento');
    // As células de turno têm um title "Dia Período: …"; os rótulos de nome não.
    const celulas = wrapper
      .findAll('span[title]')
      .filter((s: any) => /Manhã|Tarde/.test(s.attributes('title') ?? ''));
    // 2 clínicas no 2º Pavimento × 10 turnos.
    expect(celulas).toHaveLength(20);
  });

  it('marca o turno sem sala em vermelho e sinaliza a clínica e o bloco', async () => {
    const wrapper = await montar();
    await abrirAndar(wrapper, '2º Pavimento');

    const temCelulaSemSala = wrapper
      .findAll('span[title]')
      .some((s: any) => s.classes().includes('bg-paper-danger/40'));
    expect(temCelulaSemSala).toBe(true);

    const texto = wrapper.text();
    expect(texto).toContain('s/ sala');            // selo na clínica
    expect(texto).toContain('grade(s) sem sala');  // selo no bloco
  });

  it('avisa quando o cenário não foi alocado (409)', async () => {
    (api.get as any).mockRejectedValue({ response: { status: 409 } });
    const wrapper = mount(SaaVisualizacao);
    await flushPromises();

    expect(wrapper.text()).toContain('ainda não foi alocado');
  });
});
