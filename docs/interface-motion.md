# Компоненты и анимация

Стиль сохраняет цвета и шрифт ФСП. Минимальная высота кнопок, текстовых полей и пунктов меню 44 px. Ширина рамки не меняется при наведении, нажатии и фокусе

Индикатор активного раздела: отдельная полоса высотой 3 px с круглыми концами. При выборе вкладки полоса раскрывается слева направо на своём месте. На мобильном подписи и значения трёх показателей кандидата стоят в одной строке, без горизонтальной прокрутки

Выпадающие списки поддерживают стрелки, Home, End, Enter, Escape, Tab и поиск по первым буквам. Исходный select сохраняет значение формы. Меню открывается поверх карточек и окон, при нехватке места снизу размещается сверху

Модальные окна закрываются крестиком, клавишей Escape и нажатием на фон вокруг окна. Перетаскивание из окна на фон его не закрывает

Параметры движения сверены с исходниками Telegram Web A 11 октября 2026 года:

| Элемент | Время и кривая | Источник |
| --- | --- | --- |
| Раскрытие и шеврон | 300 ms, `cubic-bezier(.33, 1, .68, 1)` | [Переменные](https://github.com/Ajaxy/telegram-tt/blob/master/src/styles/_variables.scss) |
| Переход раздела и индикатор | 300 ms, `cubic-bezier(.25, 1, .5, 1)` | [Переменные](https://github.com/Ajaxy/telegram-tt/blob/master/src/styles/_variables.scss) |
| Открытие меню | 150 ms, `cubic-bezier(.2, 0, .2, 1)`, масштаб .85 → 1 | [Menu.scss](https://github.com/Ajaxy/telegram-tt/blob/master/src/components/ui/Menu.scss) |
| Закрытие меню | 200 ms, `ease-in` | [Menu.scss](https://github.com/Ajaxy/telegram-tt/blob/master/src/components/ui/Menu.scss) |
| Модальное окно | 200 ms, `ease`, смещение 16 px | [Modal.scss](https://github.com/Ajaxy/telegram-tt/blob/master/src/components/ui/Modal.scss) |
| Состояния кнопки | 200 ms, `ease`; нажатие без задержки | [Button.scss](https://github.com/Ajaxy/telegram-tt/blob/master/src/components/ui/Button.scss) |

Реализация компонентов собственная, без копирования кода Telegram. При `prefers-reduced-motion` переходы отключаются
