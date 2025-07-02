
import { Knex } from 'knex';

export async function up(knex: Knex): Promise<void> {
  return knex.schema.createTable('glpi_settings', (table) => {
    table.increments('id').primary();
    table.string('primary_color').defaultTo('#4EA8DE'); // Cor padrão azul
    table.string('secondary_color').defaultTo('#8284FA'); // Cor padrão roxo
    table.string('logo_url').nullable(); // URL da logomarca
    table.timestamp('created_at').defaultTo(knex.fn.now());
    table.timestamp('updated_at').defaultTo(knex.fn.now());
  });
}

export async function down(knex: Knex): Promise<void> {
  return knex.schema.dropTable('glpi_settings');
}
