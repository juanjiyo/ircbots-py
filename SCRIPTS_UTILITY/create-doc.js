const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, TabStopPosition, TabStopType, convertInchesToTwip } = require('docx');
const fs = require('fs');

const doc = new Document({
  sections: [{
    properties: {
      page: {
        margin: {
          top: convertInchesToTwip(1),
          right: convertInchesToTwip(1),
          bottom: convertInchesToTwip(1),
          left: convertInchesToTwip(1),
        }
      }
    },
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 400 },
        children: [
          new TextRun({
            text: "Creación de bots con Node.js y React para Discord",
            bold: true,
            size: 48,
          }),
        ],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 400 },
        children: [
          new TextRun({
            text: "Guía para desarrollar bots de Discord usando Node.js y React",
            size: 28,
          }),
        ],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 200 },
        children: [
          new TextRun({
            text: "Autor: WinterOS",
            size: 24,
          }),
        ],
      }),
      new Paragraph({
        spacing: { after: 400 },
        children: [
          new TextRun({
            text: "",
          }),
        ],
      }),
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        spacing: { after: 200 },
        children: [
          new TextRun({
            text: "1. Introducción",
            bold: true,
          }),
        ],
      }),
      new Paragraph({
        spacing: { after: 200 },
        children: [
          new TextRun({
            text: "Los bots de Discord son herramientas poderosas que permiten automatizar tareas y mejorar la experiencia en los servidores. En esta guía, aprenderemos a crear un bot utilizando Node.js y React.",
          }),
        ],
      }),
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        spacing: { after: 200 },
        children: [
          new TextRun({
            text: "2. ¿Qué es un bot de Discord?",
            bold: true,
          }),
        ],
      }),
      new Paragraph({
        spacing: { after: 200 },
        children: [
          new TextRun({
            text: "Un bot de Discord es una aplicación que puede interactuar con los usuarios y servidores de Discord. Puede realizar diversas tareas como moderar chats, reproducir música, gestionar roles y mucho más.",
          }),
        ],
      }),
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        spacing: { after: 200 },
        children: [
          new TextRun({
            text: "3. Tecnologías utilizadas",
            bold: true,
          }),
        ],
      }),
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { after: 200 },
        children: [
          new TextRun({
            text: "Node.js",
            bold: true,
          }),
        ],
      }),
      new Paragraph({
        spacing: { after: 200 },
        children: [
          new TextRun({
            text: "Node.js es un entorno de ejecución de JavaScript que permite ejecutar código JavaScript en el servidor. Es ideal para crear bots de Discord gracias a su naturaleza asíncrona y su amplia ecosistema de paquetes npm.",
          }),
        ],
      }),
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { after: 200 },
        children: [
          new TextRun({
            text: "React",
            bold: true,
          }),
        ],
      }),
      new Paragraph({
        spacing: { after: 200 },
        children: [
          new TextRun({
            text: "React es una biblioteca de JavaScript para construir interfaces de usuario. Aunque no se usa directamente en el bot, es útil para crear paneles de control web y dashboards para gestionar el bot.",
          }),
        ],
      }),
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        spacing: { after: 200 },
        children: [
          new TextRun({
            text: "4. Pasos para crear un bot de Discord",
            bold: true,
          }),
        ],
      }),
      new Paragraph({
        spacing: { after: 200 },
        children: [
          new TextRun({
            text: "Para crear un bot de Discord, sigue estos pasos:",
          }),
        ],
      }),
      new Paragraph({
        spacing: { after: 200 },
        indent: { left: convertInchesToTwip(0.5) },
        children: [
          new TextRun({
            text: "1. ",
            bold: true,
          }),
          new TextRun({
            text: "Crea una cuenta de Discord Developer y registra una nueva aplicación",
          }),
        ],
      }),
      new Paragraph({
        spacing: { after: 200 },
        indent: { left: convertInchesToTwip(0.5) },
        children: [
          new TextRun({
            text: "2. ",
            bold: true,
          }),
          new TextRun({
            text: "Instala Node.js y npm en tu sistema",
          }),
        ],
      }),
      new Paragraph({
        spacing: { after: 200 },
        indent: { left: convertInchesToTwip(0.5) },
        children: [
          new TextRun({
            text: "3. ",
            bold: true,
          }),
          new TextRun({
            text: "Inicializa un proyecto npm y instala discord.js",
          }),
        ],
      }),
      new Paragraph({
        spacing: { after: 200 },
        indent: { left: convertInchesToTwip(0.5) },
        children: [
          new TextRun({
            text: "4. ",
            bold: true,
          }),
          new TextRun({
            text: "Configura el bot con tu token de aplicación",
          }),
        ],
      }),
      new Paragraph({
        spacing: { after: 200 },
        indent: { left: convertInchesToTwip(0.5) },
        children: [
          new TextRun({
            text: "5. ",
            bold: true,
          }),
          new TextRun({
            text: "Implementa los comandos y eventos del bot",
          }),
        ],
      }),
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        spacing: { after: 200 },
        children: [
          new TextRun({
            text: "5. Conclusión",
            bold: true,
          }),
        ],
      }),
      new Paragraph({
        spacing: { after: 200 },
        children: [
          new TextRun({
            text: "Crear un bot de Discord con Node.js y React es una excelente manera de aprender desarrollo web fullstack. Los bots pueden personalizarse según las necesidades de cada servidor y ofrecen infinitas posibilidades de automatización.",
          }),
        ],
      }),
    ],
  }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync("C:\\Users\\WinterOS\\Documents\\ircbots\\Discord_Bot_Guide_WinterOS.docx", buffer);
  console.log("Documento Word creado exitosamente: Discord_Bot_Guide_WinterOS.docx");
});