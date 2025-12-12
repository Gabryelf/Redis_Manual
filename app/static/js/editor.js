   class DnDTemplateEditor {
    constructor() {
        this.templateData = {
            name: "Новый шаблон",
            description: "",
            visibility: "private",
            content: {
                sections: [],
                layout: "classic",
                style: {}
            },
            decorations: [],
            characterClass: "",
            level: 1,
            tags: []
        };

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadDefaultSections();
        this.renderEditor();
    }

    setupEventListeners() {
        // Сохранение шаблона
        document.getElementById('saveTemplate').addEventListener('click', () => this.saveTemplate());

        // Экспорт
        document.getElementById('exportPdf').addEventListener('click', () => this.exportTemplate('pdf'));
        document.getElementById('exportPng').addEventListener('click', () => this.exportTemplate('png'));
        document.getElementById('exportJson').addEventListener('click', () => this.exportTemplate('json'));

        // Добавление секций
        document.getElementById('addSection').addEventListener('click', () => this.addSection());

        // Выбор класса
        document.getElementById('characterClass').addEventListener('change', (e) => {
            this.templateData.characterClass = e.target.value;
        });
    }

    loadDefaultSections() {
        const defaultSections = [
            {
                type: "header",
                title: "Лист персонажа",
                fields: []
            },
            {
                type: "attributes",
                title: "Характеристики",
                fields: [
                    { name: "Сила", value: 10, modifier: 0 },
                    { name: "Ловкость", value: 10, modifier: 0 },
                    { name: "Телосложение", value: 10, modifier: 0 },
                    { name: "Интеллект", value: 10, modifier: 0 },
                    { name: "Мудрость", value: 10, modifier: 0 },
                    { name: "Харизма", value: 10, modifier: 0 }
                ]
            },
            {
                type: "skills",
                title: "Навыки",
                fields: []
            },
            {
                type: "combat",
                title: "Боевые параметры",
                fields: [
                    { name: "Класс брони", value: "" },
                    { name: "Инициатива", value: "" },
                    { name: "Скорость", value: "" },
                    { name: "Хиты", value: "" },
                    { name: "Кость хитов", value: "" }
                ]
            }
        ];

        this.templateData.content.sections = defaultSections;
    }

    addSection() {
        const sectionType = prompt("Тип секции (text, table, list, stats):", "text");
        if (!sectionType) return;

        const sectionTitle = prompt("Название секции:", "Новая секция");

        const newSection = {
            type: sectionType,
            title: sectionTitle,
            fields: [],
            content: ""
        };

        this.templateData.content.sections.push(newSection);
        this.renderEditor();
    }

    renderEditor() {
        const editorContainer = document.getElementById('templateEditor');
        editorContainer.innerHTML = '';

        // Рендерим каждую секцию
        this.templateData.content.sections.forEach((section, index) => {
            const sectionElement = this.createSectionElement(section, index);
            editorContainer.appendChild(sectionElement);
        });
    }

    createSectionElement(section, index) {
        const sectionDiv = document.createElement('div');
        sectionDiv.className = `template-section section-${section.type}`;
        sectionDiv.setAttribute('draggable', 'true');

        sectionDiv.innerHTML = `
            <div class="section-header">
                <h3>${section.title}</h3>
                <div class="section-actions">
                    <button onclick="editor.editSection(${index})">✏️</button>
                    <button onclick="editor.deleteSection(${index})">🗑️</button>
                </div>
            </div>
            <div class="section-content">
                ${this.renderSectionContent(section)}
            </div>
        `;

        // Добавляем обработчики drag and drop
        sectionDiv.addEventListener('dragstart', (e) => this.dragStart(e, index));
        sectionDiv.addEventListener('dragover', (e) => e.preventDefault());
        sectionDiv.addEventListener('drop', (e) => this.dropSection(e, index));

        return sectionDiv;
    }

    renderSectionContent(section) {
        switch(section.type) {
            case 'attributes':
                return this.renderAttributes(section);
            case 'combat':
                return this.renderCombatStats(section);
            case 'skills':
                return this.renderSkills(section);
            default:
                return `<textarea onchange="editor.updateSectionContent(${section.index}, this.value)">${section.content || ''}</textarea>`;
        }
    }

    renderAttributes(section) {
        let html = '<div class="attributes-grid">';
        section.fields.forEach((field, i) => {
            html += `
                <div class="attribute">
                    <label>${field.name}</label>
                    <input type="number" value="${field.value}"
                           onchange="editor.updateAttribute(${section.index}, ${i}, 'value', this.value)">
                    <div class="modifier">${this.calculateModifier(field.value)}</div>
                </div>
            `;
        });
        html += '</div>';
        return html;
    }

    calculateModifier(value) {
        const modifier = Math.floor((value - 10) / 2);
        return modifier >= 0 ? `+${modifier}` : modifier.toString();
    }

    async saveTemplate() {
        const templateName = document.getElementById('templateName').value;
        this.templateData.name = templateName;
        this.templateData.description = document.getElementById('templateDescription').value;
        this.templateData.visibility = document.getElementById('templateVisibility').value;
        this.templateData.tags = document.getElementById('templateTags').value.split(',').map(tag => tag.trim());

        try {
            const response = await fetch('/api/templates', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(this.templateData)
            });

            const result = await response.json();

            if (result.success) {
                this.showMessage('Шаблон сохранен!', 'success');
                if (!this.templateData.id) {
                    this.templateData.id = result.template_id;
                    window.history.pushState({}, '', `/editor/${result.template_id}`);
                }
            } else {
                this.showMessage('Ошибка сохранения', 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            this.showMessage('Ошибка соединения', 'error');
        }
    }

    async exportTemplate(format) {
        if (!this.templateData.id) {
            this.showMessage('Сначала сохраните шаблон', 'warning');
            return;
        }

        window.open(`/api/templates/${this.templateData.id}/export/${format}`, '_blank');
    }

    showMessage(text, type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message message-${type}`;
        messageDiv.textContent = text;
        messageDiv.style.position = 'fixed';
        messageDiv.style.top = '20px';
        messageDiv.style.right = '20px';
        messageDiv.style.padding = '15px';
        messageDiv.style.borderRadius = '5px';
        messageDiv.style.zIndex = '1000';

        if (type === 'success') {
            messageDiv.style.background = '#d4edda';
            messageDiv.style.color = '#155724';
        } else if (type === 'error') {
            messageDiv.style.background = '#f8d7da';
            messageDiv.style.color = '#721c24';
        } else {
            messageDiv.style.background = '#fff3cd';
            messageDiv.style.color = '#856404';
        }

        document.body.appendChild(messageDiv);

        setTimeout(() => {
            messageDiv.remove();
        }, 3000);
    }

    // Методы для редактирования
    editSection(index) {
        const newTitle = prompt("Новое название секции:", this.templateData.content.sections[index].title);
        if (newTitle) {
            this.templateData.content.sections[index].title = newTitle;
            this.renderEditor();
        }
    }

    deleteSection(index) {
        if (confirm("Удалить эту секцию?")) {
            this.templateData.content.sections.splice(index, 1);
            this.renderEditor();
        }
    }

    updateSectionContent(sectionIndex, content) {
        this.templateData.content.sections[sectionIndex].content = content;
    }

    updateAttribute(sectionIndex, fieldIndex, field, value) {
        this.templateData.content.sections[sectionIndex].fields[fieldIndex][field] = parseInt(value);
        this.renderEditor();
    }

    // Drag and drop
    dragStart(e, index) {
        e.dataTransfer.setData('text/plain', index);
    }

    dropSection(e, targetIndex) {
        e.preventDefault();
        const sourceIndex = e.dataTransfer.getData('text/plain');

        // Перемещаем секцию
        const [movedSection] = this.templateData.content.sections.splice(sourceIndex, 1);
        this.templateData.content.sections.splice(targetIndex, 0, movedSection);

        this.renderEditor();
    }
}

// Инициализация редактора
let editor;
document.addEventListener('DOMContentLoaded', () => {
    editor = new DnDTemplateEditor();
});