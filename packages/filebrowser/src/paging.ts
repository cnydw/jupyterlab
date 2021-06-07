import { Widget } from '@lumino/widgets';

import { FilterFileBrowserModel } from './model';


export class Paging extends Widget {
  /**
   * Construct a new file browser directory listing widget.
   *
   * @param model - The file browser view model.
   */
  constructor(options: Paging.IOptions) {
    super();
    this._model = options.model;
    this._model.fileChanged.connect(this._onchange, this);
    this._model.refreshed.connect(this._onchange, this);
    this._model.pathChanged.connect(this._onchange, this);
    this.addClass("jp-DirPagination");
    this._onchange();
  }


  /**
   * Get the model used by the listing.
   */
  get model(): FilterFileBrowserModel {
    return this._model;
  }


  /**
   * Update the node
   */
  private _onchange(): void {
    const max_page = this._model.max_page;
    const page = this._model.page;

    while (this.node.firstChild) {
      this.node.removeChild(this.node.firstChild);
    }

    // Don't show the paging widget if paging is not needed
    if (this._model.max_page === 1) {
      return;
    }

    /* 
    if max_page <= 7
      show all items
    otherwise
    if page <= 4
     show 1-5 and the right ellipse
    if max_page-3 <= page
     show the left ellipse and max_page-4 to max_page
    if 4 < page < max_page-3
     show left ellipse, page-1, page, page+1, right ellipse    
    */
    if ( max_page <= 7 ) {
      for (let i = 1; i <= max_page; i++) {
        this._createButton(i, page);
      }
    } else if (page <= 4) {
      for (let i = 1; i <= 5; i++) {
        this._createButton(i, page);
      }
      this._createEllipse();
      this._createButton(max_page, page);
    } else if (page >= max_page - 3) {
      this._createButton(1, page);
      this._createEllipse();
      for (let i = max_page-4; i <= max_page; i++) {
        this._createButton(i, page);
      }
    } else {
      this._createButton(1, page);
      this._createEllipse();
      this._createButton(page - 1, page);
      this._createButton(page, page);
      this._createButton(page + 1, page);
      this._createEllipse();
      this._createButton(max_page, page);
    }
  }

  private _createButton(i:number, activePage:number) {
    let button = document.createElement("a");
    button.textContent = i.toString();
    button.onclick = () => {
      this._model.cd_page(i);
    }
    if (i === activePage) {
      button.className = 'active';
    }
    this.node.appendChild(button);

  }

  // TODO: remove the hover effect 
  private _createEllipse() {
    let button = document.createElement("span");
    button.textContent = "..."
    this.node.appendChild(button);
  }

  private _model: FilterFileBrowserModel;
}

export namespace Paging {
  /**
   * An options object for initializing a file browser directory listing.
   */
  export interface IOptions {
    /**
     * A file browser model instance.
     */
    model: FilterFileBrowserModel;

  }
}