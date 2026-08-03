import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';

import PlanilhaEditavel, { type Coluna } from '../PlanilhaEditavel.vue';

const COLUNAS: Coluna[] = [
  { chave: 'nome', rotulo: 'Clínica' },
  { chave: 't0', rotulo: 'SegM', editavel: true },
  { chave: 't1', rotulo: 'SegT', editavel: true },
];

const LINHAS = [
  { id: 1, nome: 'CARDIOLOGIA', t0: 3, t1: 5 },
  { id: 2, nome: 'ORTOPEDIA', t0: 2, t1: 0 },
];

function montar(extra: Record<string, unknown> = {}) {
  return mount(PlanilhaEditavel, {
    props: { colunas: COLUNAS, linhas: LINHAS, ...extra },
  });
}

describe('PlanilhaEditavel.vue', () => {
  it('desenha uma coluna por definição e uma linha por registro', () => {
    const wrapper = montar();

    expect(wrapper.findAll('thead th').map(th => th.text())).toEqual([
      'Clínica', 'SegM', 'SegT',
    ]);
    expect(wrapper.findAll('tbody tr')).toHaveLength(2);
  });

  it('só transforma em campo o que foi marcado como editável', () => {
    const wrapper = montar();

    // 2 linhas × 2 colunas editáveis; a coluna de nome fica como texto.
    expect(wrapper.findAll('input[type=number]')).toHaveLength(4);
    expect(wrapper.find('tbody tr td').text()).toContain('CARDIOLOGIA');
  });

  it('mostra o valor de cada célula', () => {
    const campos = montar().findAll('input[type=number]');
    expect(campos.map(c => (c.element as HTMLInputElement).value)).toEqual(
      ['3', '5', '2', '0']
    );
  });

  it('emite a alteração com a linha e a coluna de origem', async () => {
    const wrapper = montar();
    await wrapper.findAll('input[type=number]')[0].setValue('7');

    const eventos = wrapper.emitted('editar');
    expect(eventos).toHaveLength(1);
    expect(eventos![0][0]).toMatchObject({ chave: 't0', valor: 7 });
    expect((eventos![0][0] as any).linha.nome).toBe('CARDIOLOGIA');
  });

  it('não emite quando o valor não mudou', async () => {
    const wrapper = montar();
    await wrapper.findAll('input[type=number]')[0].setValue('3');

    expect(wrapper.emitted('editar')).toBeUndefined();
  });

  it('recusa valor abaixo do mínimo e devolve o campo ao que estava', async () => {
    const wrapper = montar();
    const campo = wrapper.findAll('input[type=number]')[0];
    await campo.setValue('-5');

    expect(wrapper.emitted('editar')).toBeUndefined();
    expect((campo.element as HTMLInputElement).value).toBe('3');
  });

  it('respeita o máximo quando informado', async () => {
    const wrapper = montar({ max: 10 });
    const campo = wrapper.findAll('input[type=number]')[0];
    await campo.setValue('50');

    expect(wrapper.emitted('editar')).toBeUndefined();
    expect((campo.element as HTMLInputElement).value).toBe('3');
  });

  it('desenha o rodapé de totais quando recebido', () => {
    const wrapper = montar({ rodape: { nome: 'Total', t0: 5, t1: 5 } });

    const rodape = wrapper.findAll('tfoot td').map(td => td.text());
    expect(rodape).toEqual(['Total', '5', '5']);
  });

  it('avisa quando não há nada para exibir', () => {
    const wrapper = montar({ linhas: [] });
    expect(wrapper.text()).toContain('Nada para exibir');
  });

  it('insere uma linha separadora quando o grupo muda', () => {
    const wrapper = montar({
      rotuloGrupo: (l: any) => (l.nome === 'CARDIOLOGIA' ? '2º Pavimento' : '3º Pavimento'),
    });

    const separadores = wrapper
      .findAll('tbody tr')
      .filter(tr => tr.find('td[colspan]').exists())
      .map(tr => tr.text());
    expect(separadores).toEqual(['2º Pavimento', '3º Pavimento']);
  });

  it('não desenha separadores sem rotuloGrupo', () => {
    const wrapper = montar();
    const comColspan = wrapper
      .findAll('tbody tr')
      .filter(tr => tr.find('td[colspan]').exists());
    expect(comColspan).toHaveLength(0);
  });

  it('aplica o realce devolvido por corDaCelula', () => {
    const wrapper = mount(PlanilhaEditavel, {
      props: {
        colunas: COLUNAS,
        linhas: LINHAS,
        corDaCelula: (linha: any, coluna: Coluna) =>
          coluna.chave === 't1' && linha.t1 === 0 ? 'bg-paper-danger/10' : '',
      },
    });

    const celulas = wrapper.findAll('tbody tr')[1].findAll('td');
    expect(celulas[2].classes()).toContain('bg-paper-danger/10');
  });

  it('colar do Excel preenche o retângulo a partir da célula focada', async () => {
    const wrapper = montar();
    const campo = wrapper.findAll('input[type=number]')[0];

    // Duas linhas × duas colunas, no formato TSV que o Excel coloca na área
    // de transferência.
    await campo.trigger('paste', {
      clipboardData: { getData: () => '11\t12\n21\t22' },
    });

    const eventos = wrapper.emitted('editar');
    expect(eventos).toHaveLength(4);
    expect(eventos!.map(e => (e[0] as any).valor)).toEqual([11, 12, 21, 22]);
    expect((eventos![3][0] as any).linha.nome).toBe('ORTOPEDIA');
  });

  it('colar um valor único segue o fluxo normal do campo', async () => {
    const wrapper = montar();
    await wrapper.findAll('input[type=number]')[0].trigger('paste', {
      clipboardData: { getData: () => '9' },
    });

    // Sem tabulação nem quebra de linha, o navegador cuida — nada é emitido aqui.
    expect(wrapper.emitted('editar')).toBeUndefined();
  });

  it('colar ignora células que cairiam fora da planilha', async () => {
    const wrapper = montar();
    const ultimo = wrapper.findAll('input[type=number]')[3]; // linha 2, última coluna

    await ultimo.trigger('paste', {
      clipboardData: { getData: () => '99\t88\n77\t66' },
    });

    // Só a própria célula existe; o resto extrapola linhas e colunas.
    const eventos = wrapper.emitted('editar');
    expect(eventos).toHaveLength(1);
    expect(eventos![0][0]).toMatchObject({ chave: 't1', valor: 99 });
  });
});
