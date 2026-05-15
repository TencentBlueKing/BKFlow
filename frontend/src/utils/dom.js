/**
* Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
* Edition) available.
* Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
* Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
* http://opensource.org/licenses/MIT
* Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
* an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
* specific language governing permissions and limitations under the License.
*/
const dom = {
  /**
   * 检查一个元素是否包含另一个元素
   * 提供跨浏览器兼容的元素包含关系检测
   * @param {Element} root - 父容器元素
   * @param {Element} el - 要检查的子元素
   * @returns {boolean} 如果 root 包含 el 则返回 true，否则返回 false
   * 实现逻辑：
   * 1. 优先使用现代浏览器的 compareDocumentPosition API
   * 2. 降级使用 contains 方法（排除自身相等的情况）
   * 3. 最后使用手动遍历父节点的兼容方式
   */
  nodeContains(root, el) {
    // 方法1：使用 compareDocumentPosition API（现代浏览器）
    // 返回值 & 16 表示 el 被 root 包含
    if (root.compareDocumentPosition) {
      return root === el || !!(root.compareDocumentPosition(el) & 16);
    }
    // 方法2：使用 contains 方法（IE9+）
    // 确保 el 是元素节点且不等于 root 自身
    if (root.contains && el.nodeType === 1) {
      return root.contains(el) && root !== el;
    }
    // 方法3：手动遍历父节点链（兼容旧浏览器）
    let node = el.parentNode;
    while (node) {
      if (node === root) return true;
      node = node.parentNode;
    }
    return false;
  },
  parentClsContains(cls, el) {
    if (el.classList.contains(cls)) {
      return true;
    }
    let node = el.parentNode;
    while (node) {
      if (node.classList && node.classList.contains(cls)) return true;
      node = node.parentNode;
    }
    return false;
  },
  getElementScrollCoords(element) {
    let actualLeft = element.offsetLeft;
    let actualTop = element.offsetTop;
    let current = element.offsetParent;
    while (current !== null) {
      // 注意要加上边界宽度
      actualLeft += (current.offsetLeft + current.clientLeft);
      actualTop += (current.offsetTop + current.clientTop);
      current = current.offsetParent;
    }
    return { x: actualLeft, y: actualTop };
  },
  setPageTabIcon(path) {
    const link = document.querySelector('link[rel*="icon"]') || document.createElement('link');
    link.type = 'image/x-icon';
    link.rel = 'shortcut icon';
    link.href = path;
    document.getElementsByTagName('head')[0].appendChild(link);
  },
};

export default dom;
