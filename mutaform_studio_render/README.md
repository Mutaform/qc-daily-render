# Mutaform Studio Render

Недеструктивный студийный рендер в стиле Marmoset для Blender 5.2. Одна кнопка
строит студийную сцену (HDRI-свет, единый материал, ловец контактной тени,
пост-обработка в стиле Marmoset), другая — снимает текущий ракурс вьюпорта в PNG
с альфой. Restore возвращает сцену ровно в исходное состояние.

## Установка (Blender 5.2+)

1. `Edit → Preferences → Get Extensions → ▼ → Install from Disk…`
2. Выбрать `mutaform_studio_render_vX.Y.Z_extension.zip`.
3. Панель появится: `View3D → N-панель → вкладка «QC Render»`.

## Как пользоваться

1. **Setup Render Scene** — строит студию, вьюпорт переключается в Rendered с
   нашим HDRI и рамкой будущего кадра. Обычная навигация вьюпорта сохраняется.
   До Setup настройки в табах неактивны.
2. Летаешь вьюпортом, ищешь ракурс. Материал — над свитком Camera Settings,
   свет/пост — внутри него, разрешение/сэмплы/движок — в Render Settings.
3. **Render** — ставит камеру по текущему виду, рендерит ровно то, что в рамке,
   сохраняет авто-нумерованный PNG с альфой, камеру убирает. Вид не трогается.
   **Open Folder** рядом открывает папку с рендерами.
4. **Restore (exit)** — полностью откатывает сцену (включая настройки устройств
   рендера) и удаляет всё созданное.

## Вкладки

- **Camera Settings** — Use Default Material (Base Color/Roughness/Metallic);
  свиток: FOV, HDRI Brightness/Rotation, Post Effect (Tone Mapping, Exposure,
  Highlights/Midtones/Shadows, Clarity, Contrast, Saturation), Sharpen,
  Vignette, Frame Guide + Background (цвет подложки превью); ниже — Wireframe.
- **Render Settings** — движок превью и рендера (Cycles / EEVEE), разрешение
  (×0.5 / ×2), Samples, Denoiser, Ground Shadow, папка и имя вывода
  (авто-нумерация; при пустой папке показывается реальный путь сохранения).

## Скорость и качество

- При Setup аддон сам выбирает быстрейшую конфигурацию под машину: лучший
  доступный backend (OptiX → CUDA → HIP → oneAPI → Metal), только GPU (без
  CPU-гибрида), persistent data. На выходе из студии всё восстанавливается.
- Нет NVIDIA — денойзер OptiX сам заменяется на OpenImageDenoise.
- EEVEE — быстрый превью-режим: та же сцена, но без тени от пола (ловец теней —
  фича Cycles).

Финальный кадр — с прозрачной плёнкой (альфа), поэтому тень композится на любой
фон.
