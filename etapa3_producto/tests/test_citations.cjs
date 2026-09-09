const { test } = require('node:test');
const assert = require('node:assert/strict');
const { citationSegments } = require('../frontend/citations.js');

const sources = [{ chunk_id: 'doc-21719-p1' }, { chunk_id: 'art-1' }];
test('reemplaza IDs por números sin cambiar el texto', () => {
  assert.deepEqual(citationSegments('Ley [doc-21719-p1]. Artículo [art-1].', sources),
    [{ text: 'Ley ' }, { number: 1 }, { text: '. Artículo ' }, { number: 2 }, { text: '.' }]);
});
test('una fuente repetida conserva el mismo número', () => {
  assert.deepEqual(citationSegments('[doc-21719-p1][art-1][doc-21719-p1]', sources),
    [{ number: 1 }, { number: 2 }, { number: 1 }]);
});
test('referencias desconocidas permanecen como texto, sin enlace engañoso', () => {
  assert.deepEqual(citationSegments('[inventada] y [art-1]', sources), [{ text: '[inventada] y ' }, { number: 2 }]);
});
test('HTML y otros corchetes son texto, no se interpretan', () => {
  assert.deepEqual(citationSegments('<img src=x onerror=alert(1)> [nota] [art-1]', sources),
    [{ text: '<img src=x onerror=alert(1)> [nota] ' }, { number: 2 }]);
});
test('no altera mensajes sin citas ni mensajes vacíos', () => {
  assert.deepEqual(citationSegments('Hola Felipe', []), [{ text: 'Hola Felipe' }]);
  assert.deepEqual(citationSegments('', []), []);
});
test('numeración independiente por respuesta; IDs no son expresiones regulares', () => {
  assert.deepEqual(citationSegments('[art-1]', [{ chunk_id: 'art-1' }]), [{ number: 1 }]);
  assert.deepEqual(citationSegments('[a.b] [axb]', [{ chunk_id: 'a.b' }]), [{ number: 1 }, { text: ' [axb]' }]);
});
