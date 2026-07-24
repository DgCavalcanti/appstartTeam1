import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';

import FiltroAlocacao from '../FiltroAlocacao.vue';

interface Linha { nome: string; bloco: string | null; pavimento: string | null }

const LINHAS: Linha[] = [
  { nome: 'OFTALMOLOGIA', bloco: 'Bloco E', pavimento: '2º Pavimento' },
  { nome: 'ORTOPEDIA', bloco: 'Bloco E', pavimento: '3º Pavimento' },
  { nome: 'CARDIOLOGIA', bloco: 'Bloco F', pavimento: '5º Pavimento' },
  { nome: 'PEDIATRIA', bloco: 'Bloco F', pavimento: '2º Pavimento' },
];

/** Monta o componente e expõe as linhas filtradas via slot. */
function montar(linhas: Linha[] = LINHAS) {
  return mount(FiltroAlocacao, {
    props: { linhas },
    slots: {
      default: `
        <template #default="{ filtradas }">
          <ul>
            <li v-for="l in filtradas" :key="l.nome" class="item">{{ l.nome }}</li>
          </ul>
        </template>
      `,
    },
  });
}

const nomes = (w: any) => w.findAll('.item').map((li: any) => li.text());
const buscaEl = (w: any) => w.find('input[type=search]');
const selectBloco = (w: any) => w.findAll('select')[0];
const selectPavimento = (w: any) => w.findAll('select')[1];

describe('FiltroAlocacao.vue', () => {
  it('sem filtro, expõe todas as linhas', () => {
    const wrapper = montar();
    expect(nomes(wrapper)).toHaveLength(4);
    expect(wrapper.text()).toContain('Mostrando 4 de 4');
  });

  it('lista os blocos e pavimentos distintos, ordenados', () => {
    const wrapper = montar();
    expect(selectBloco(wrapper).findAll('option').map((o: any) => o.text()))
      .toEqual(['Todos os blocos', 'Bloco E', 'Bloco F']);
    expect(selectPavimento(wrapper).findAll('option').map((o: any) => o.text()))
      .toEqual(['Todos os pavimentos', '2º Pavimento', '3º Pavimento', '5º Pavimento']);
  });

  it('busca pelo nome, ignorando acento e caixa', async () => {
    const wrapper = montar();
    await buscaEl(wrapper).setValue('cardiologia');
    expect(nomes(wrapper)).toEqual(['CARDIOLOGIA']);
  });

  it('a busca não casa bloco nem pavimento — só o nome', async () => {
    const wrapper = montar();
    await buscaEl(wrapper).setValue('Bloco E');
    // Nenhuma clínica se chama "Bloco E"; para filtrar por bloco há o seletor.
    expect(nomes(wrapper)).toHaveLength(0);
  });

  it('filtra por bloco', async () => {
    const wrapper = montar();
    await selectBloco(wrapper).setValue('Bloco E');
    expect(nomes(wrapper).sort()).toEqual(['OFTALMOLOGIA', 'ORTOPEDIA']);
  });

  it('filtra por pavimento cruzando blocos', async () => {
    const wrapper = montar();
    await selectPavimento(wrapper).setValue('2º Pavimento');
    expect(nomes(wrapper).sort()).toEqual(['OFTALMOLOGIA', 'PEDIATRIA']);
  });

  it('combina bloco E pavimento (E)', async () => {
    const wrapper = montar();
    await selectBloco(wrapper).setValue('Bloco F');
    await selectPavimento(wrapper).setValue('2º Pavimento');
    expect(nomes(wrapper)).toEqual(['PEDIATRIA']);
  });

  it('o botão limpar zera todos os filtros', async () => {
    const wrapper = montar();
    await buscaEl(wrapper).setValue('oftalmo');
    await selectBloco(wrapper).setValue('Bloco E');
    expect(nomes(wrapper).length).toBeLessThan(4);

    await wrapper.find('button').trigger('click'); // "limpar"
    expect(nomes(wrapper)).toHaveLength(4);
    expect((buscaEl(wrapper).element as HTMLInputElement).value).toBe('');
  });

  it('não mostra o botão limpar quando não há filtro ativo', () => {
    const wrapper = montar();
    expect(wrapper.find('button').exists()).toBe(false);
  });

  it('ignora linhas sem bloco/pavimento nas opções dos seletores', () => {
    const wrapper = montar([
      { nome: 'SEM SALA', bloco: null, pavimento: null },
      { nome: 'CARDIOLOGIA', bloco: 'Bloco F', pavimento: '5º Pavimento' },
    ]);
    expect(selectBloco(wrapper).findAll('option').map((o: any) => o.text()))
      .toEqual(['Todos os blocos', 'Bloco F']);
  });
});
