export const fontStyleMap = {
  normal: {
    getStyle() {
      return {};
    },
  },
  bold: {
    getStyle() {
      return {
        fontWeight: 700,
      };
    },
  },
  italic: {
    getStyle() {
      return {
        fontStyle: 'italic',
      };
    },
  },
};
export const processConfigItem = (configItem) => {
  if (!configItem) return null;

  const { key, value, renders } = configItem;
  const processed = {
    key,
    value,
    hasProgress: false,
    hasLink: false,
    linkUrl: '',
    text: {
      color: '#4D4F56',
      highlightStyle: {},
      highlightBg: '',
    },
    progess: {
      progressColor: '',
      Range: [0, 100],
    },

  };

  if (!renders || !renders.length) {
    return processed;
  }

  // 处理link
  const linkRender = renders.find(r => r.type === 'link');
  if (linkRender) {
    processed.hasLink = true;
    processed.linkUrl = linkRender.url;
  }

  // 处理highlight和progress (只能有一个)
  const highlightRender = renders.find(r => r.type === 'highlight');
  const progressRender = renders.find(r => r.type === 'progress');

  if (progressRender) {
    processed.hasProgress = true;
    processed.progess.Range = progressRender.range || [0, 100];
    processed.progess.progressColor = progressRender.color || '#3A83FF';
  } else if (highlightRender && highlightRender.conditions && highlightRender.conditions.length) {
    // 根据条件确定是否高亮
    const numValue = !isNaN(Number(value)) ? Number(value) : value;

    for (const condition of highlightRender.conditions) {
      let isMatch = false;

      switch (condition.condition) {
        case '>':
          isMatch = numValue > condition.value;
          break;
        case '<':
          isMatch = numValue < condition.value;
          break;
        case '>=':
          isMatch = numValue >= condition.value;
          break;
        case '<=':
          isMatch = numValue <= condition.value;
          break;
        case '=':
          isMatch = value === condition.value;
          break;
      }

      if (isMatch) {
        processed.hasHighlight = true;
        processed.text.color = condition.color || '#4D4F56';
        Object.assign(processed.text.highlightStyle, fontStyleMap[condition.fontStyle || 'normal'].getStyle());
        processed.text.highlightBg = condition.bgColor || '';
        break;
      }
    }
  }

  return processed;
};
export const transformNodeConfigToRenderItems = node => node.config.map(config => processConfigItem(config));

export const getCopyNode = (node) => {
  const tempNode = JSON.parse(JSON.stringify(node));
  tempNode.name = `${tempNode.name}(副本)`;
  tempNode.id = new Date().getTime()
    .toString();
  return tempNode;
};
