// Checks the pure unit logic inside index.html. Run: node tests/units.test.mjs
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const src = html.match(/<script id="units">([\s\S]*?)<\/script>/)[1];
const { fraction, convert, amount, temps } = new Function(`${src}; return { fraction, convert, amount, temps };`)();

assert.equal(fraction(0.333), '⅓');
assert.equal(fraction(1.5), '1½');
assert.equal(fraction(0.98), '1');
assert.equal(fraction(2.75), '2¾');
assert.equal(fraction(0.01), '0.01');

const ing = (quantity, unit, scalable = true) => ({ quantity, unit, ingredient: 'x', note: null, scalable });
assert.equal(amount(ing(1, 'tsp'), 48, 'imperial'), '1 cup');           // 48 tsp -> 1 cup
assert.equal(amount(ing(1, 'tbsp'), 2, 'imperial'), '2 tbsp');
assert.equal(amount(ing(1, 'cup'), 1.5, 'imperial'), '1½ cups');
assert.equal(amount(ing(1, 'cup'), 1, 'metric'), '240 ml');
assert.equal(amount(ing(1, 'tsp'), 1, 'metric'), '5 ml');
assert.equal(amount(ing(5, 'cup'), 1, 'metric'), '1.18 l');
assert.equal(amount(ing(250, 'ml'), 1, 'imperial'), '1 cup');
assert.equal(amount(ing([2, 3], 'clove'), 2, 'imperial'), '4–6 cloves');
assert.equal(amount(ing(200, 'g'), 1.5, 'metric'), '300 g');
assert.equal(amount(ing(1, 'pinch', false), 3, 'imperial'), '1 pinch');
assert.equal(amount(ing(null, null, false), 3, 'imperial'), '');
assert.equal(amount(ing(2, null), 1.5, 'imperial'), '3');

assert.equal(temps('Bake at 350°F for 1 hour.', 'metric'), 'Bake at 175°C for 1 hour.');
assert.equal(temps('Heat to 180 degrees Celsius.', 'imperial'), 'Heat to 355°F.');
assert.equal(temps('Add 2 C flour.', 'metric'), 'Add 2 C flour.');            // cups, not Celsius
assert.equal(temps('Bake at 350°F.', 'imperial'), 'Bake at 350°F.');

console.log('unit tests passed');
