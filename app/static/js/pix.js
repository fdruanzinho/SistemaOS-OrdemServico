/**
 * Gerador de "Pix Copia e Cola" (BR Code) no padrão do Banco Central
 * e renderização do QR Code correspondente.
 *
 * Uso:
 *   gerarQrCodePix({
 *     chave: "11999999999",
 *     nomeRecebedor: "MINHA EMPRESA",
 *     cidade: "SAO PAULO",
 *     valor: 150.00,           // opcional
 *     identificador: "OS1234", // opcional, até 25 caracteres alfanuméricos
 *     elementoId: "qrcodePix"  // id da div onde o QR será desenhado
 *   });
 */

function _piField(id, value) {
  const len = String(value.length).padStart(2, "0");
  return `${id}${len}${value}`;
}

function _piLimparTexto(texto, tamanhoMax) {
  return (texto || "")
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "") // remove acentos
    .replace(/[^A-Za-z0-9 ]/g, "")
    .toUpperCase()
    .slice(0, tamanhoMax);
}

function _piCrc16(payload) {
  let crc = 0xFFFF;
  for (let i = 0; i < payload.length; i++) {
    crc ^= payload.charCodeAt(i) << 8;
    for (let j = 0; j < 8; j++) {
      crc = (crc & 0x8000) ? ((crc << 1) ^ 0x1021) : (crc << 1);
      crc &= 0xFFFF;
    }
  }
  return crc.toString(16).toUpperCase().padStart(4, "0");
}

function montarPayloadPix({ chave, nomeRecebedor, cidade, valor, identificador }) {
  const nome = _piLimparTexto(nomeRecebedor, 25) || "RECEBEDOR";
  const cid = _piLimparTexto(cidade, 15) || "BRASIL";
  const txid = (identificador || "***").replace(/[^A-Za-z0-9]/g, "").slice(0, 25) || "***";

  const merchantAccountInfo = _piField("00", "BR.GOV.BCB.PIX") + _piField("01", chave);
  const additionalData = _piField("05", txid);

  let payload =
    _piField("00", "01") +
    _piField("26", merchantAccountInfo) +
    _piField("52", "0000") +
    _piField("53", "986");

  if (valor && parseFloat(valor) > 0) {
    payload += _piField("54", parseFloat(valor).toFixed(2));
  }

  payload +=
    _piField("58", "BR") +
    _piField("59", nome) +
    _piField("60", cid) +
    _piField("62", additionalData);

  payload += "6304"; // indica que o CRC vem a seguir, já contando com esses 4 caracteres
  const crc = _piCrc16(payload);
  return payload + crc;
}

function gerarQrCodePix({ chave, nomeRecebedor, cidade, valor, identificador, elementoId }) {
  const container = document.getElementById(elementoId);
  if (!container) return null;
  container.innerHTML = "";

  if (!chave) {
    container.innerHTML = '<div class="alert alert-warning py-2 mb-0 small">' +
      'Chave Pix da empresa não configurada. Defina EMPRESA_PIX_CHAVE, ' +
      'EMPRESA_PIX_NOME e EMPRESA_PIX_CIDADE no arquivo .env do sistema.</div>';
    return null;
  }

  const payload = montarPayloadPix({ chave, nomeRecebedor, cidade, valor, identificador });

  // eslint-disable-next-line no-undef
  new QRCode(container, {
    text: payload,
    width: 200,
    height: 200,
  });

  return payload;
}
